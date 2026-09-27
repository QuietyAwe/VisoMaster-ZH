import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms


# Assuming Equirec2Perspec_vr and Perspec2Equirec_vr are in app.processors.external
from app.processors.external.Equirec2Perspec_vr import Equirectangular as E2P_Equirectangular
from app.processors.external.Perspec2Equirec_vr import Perspective as P2E_Perspective


def _get_sobel_kernels(device):
    sobel_x_kernel = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]], device=device, dtype=torch.float32).reshape(1, 1, 3, 3)
    sobel_y_kernel = torch.tensor([[-1., -2., -1.], [0., 0., 0.], [1., 2., 1.]], device=device, dtype=torch.float32).reshape(1, 1, 3, 3)
    return sobel_x_kernel, sobel_y_kernel

class EquirectangularConverter:
    def __init__(self, equirect_image_data_rgb_uint8: np.ndarray, device: torch.device):
        """
        Initializes with equirectangular image data.
        :param equirect_image_data_rgb_uint8: NumPy array (H, W, C) in RGB, uint8 format.
        :param device: PyTorch device to use.
        """

        self.device = device
        # 支持 numpy(HWC RGB uint8) 与 torch(CHW RGB uint8) 两种输入；已是张量时直接复用，
        # 避免每帧对 8K 全景做冗余 H2D 传输（实测每帧数毫秒）。
        # numpy 路径的 ascontiguousarray 防御负步长视图（如 frame[..., ::-1]）。
        if isinstance(equirect_image_data_rgb_uint8, torch.Tensor):
            self.equirect_tensor_cxhxw_rgb_uint8 = equirect_image_data_rgb_uint8.to(self.device)
        else:
            self.equirect_tensor_cxhxw_rgb_uint8 = torch.from_numpy(
                np.ascontiguousarray(equirect_image_data_rgb_uint8)
            ).permute(2,0,1).to(self.device)
        
        self.channels, self.height, self.width = self.equirect_tensor_cxhxw_rgb_uint8.shape
        self.e2p_instance = E2P_Equirectangular(self.equirect_tensor_cxhxw_rgb_uint8)

    def calculate_theta_phi_from_bbox(self, bbox_np: np.ndarray):
        x1, y1, x2, y2 = map(int, bbox_np)
        x_center = (x1 + x2) / 2
        y_center = (y1 + y2) / 2
        
        theta = (x_center / self.width - 0.5) * 360.0
        phi = -(y_center / self.height - 0.5) * 180.0 # Negative because image y is top-to-bottom

        return theta, phi

    def get_perspective_crop(self, FOV: float, THETA: float, PHI: float, height: int, width: int) -> torch.Tensor:
        """
        Returns a perspective crop as a Torch tensor (C, H, W) in RGB, uint8 format, on GPU.
        """
        # E2P_Equirectangular.GetPerspective now returns a Torch tensor (CHW, RGB, uint8)
        persp_torch_cxhxw_rgb_uint8 = self.e2p_instance.GetPerspective(FOV, THETA, PHI, height, width)
        return persp_torch_cxhxw_rgb_uint8

    def project_pano_kps_to_crop(self, kps_pano_xy: np.ndarray, crop_fov: float,
                                 crop_theta: float, crop_phi: float,
                                 crop_width: int, crop_height: int) -> np.ndarray:
        """把全景像素坐标的关键点精确投影到透视 crop 坐标。

        与 GetPerspective 的采样几何严格互逆（同一旋转构造与投影公式），
        换算本身零近似误差，总精度取决于全景端关键点定位质量。
        比在 crop 上二次检测（约 4.4ms/脸）便宜约三个数量级。
        """
        kps_pano_xy = np.asarray(kps_pano_xy, dtype=np.float64)
        # 全景像素 → 球面方向向量（与 GetPerspective 的反向映射一致）
        equ_cx = (self.width - 1) / 2.0
        equ_cy = (self.height - 1) / 2.0
        lon = (kps_pano_xy[:, 0] - equ_cx) / equ_cx * np.pi
        lat = -(kps_pano_xy[:, 1] - equ_cy) / equ_cy * (np.pi / 2.0)
        clat = np.cos(lat)
        vx, vy, vz = clat * np.cos(lon), clat * np.sin(lon), np.sin(lat)

        # 旋转矩阵（与 GetPerspective 相同构造，ROLL=0），逆变换用 R^T
        x_axis = np.array([1.0, 0.0, 0.0], np.float64)
        y_axis = np.array([0.0, 1.0, 0.0], np.float64)
        z_axis = np.array([0.0, 0.0, 1.0], np.float64)
        R1, _ = cv2.Rodrigues(z_axis * np.radians(crop_theta))
        R2, _ = cv2.Rodrigues(np.dot(R1, y_axis) * np.radians(-crop_phi))
        R = R2 @ R1

        # 球面方向 → 相机坐标（p = R^T · v）
        px = R[0, 0] * vx + R[1, 0] * vy + R[2, 0] * vz
        py = R[0, 1] * vx + R[1, 1] * vy + R[2, 1] * vz
        pz = R[0, 2] * vx + R[1, 2] * vy + R[2, 2] * vz

        # 相机坐标 → crop 像素（与 GetPerspective 的 persp 网格一致：
        # x_3d=1, y_3d=persp_xx, z_3d=-persp_yy；linspace 端点映射）
        wFOV = float(crop_fov)
        hFOV = crop_height / crop_width * wFOV
        w_len = np.tan(np.radians(wFOV / 2.0))
        h_len = np.tan(np.radians(hFOV / 2.0))
        eps = 1e-6
        safe_px = np.where(np.abs(px) < eps, eps, px)
        persp_xx = py / safe_px
        persp_yy = -pz / safe_px
        u = (persp_xx + w_len) / (2 * w_len) * (crop_width - 1)
        v = (persp_yy + h_len) / (2 * h_len) * (crop_height - 1)
        return np.stack([u, v], axis=1).astype(np.float32)


class PerspectiveConverter:
    def __init__(self, base_equirect_image_data_rgb_uint8: np.ndarray, device: torch.device):
        """
        Initializes with the base equirectangular image data (used for dimensions and as background).
        :param base_equirect_image_data_rgb_uint8: NumPy array (H, W, C) in RGB, uint8 format.
        :param device: PyTorch device to use.
        """

        self.device = device
        # 支持 numpy(HWC RGB uint8) 与 torch(CHW RGB uint8) 两种输入；已是张量时直接复用，
        # 避免每帧对 8K 全景做冗余 H2D 传输。numpy 路径防御负步长视图。
        if isinstance(base_equirect_image_data_rgb_uint8, torch.Tensor):
            self.base_equirect_tensor_cxhxw_rgb_uint8 = base_equirect_image_data_rgb_uint8.to(self.device)
        else:
            self.base_equirect_tensor_cxhxw_rgb_uint8 = torch.from_numpy(
                np.ascontiguousarray(base_equirect_image_data_rgb_uint8)
            ).permute(2,0,1).to(self.device)
        self.orig_channels, self.orig_height, self.orig_width = self.base_equirect_tensor_cxhxw_rgb_uint8.shape
        self.sobel_x_kernel, self.sobel_y_kernel = _get_sobel_kernels(self.device)

    def _apply_feathering(self, mask_torch: torch.Tensor) -> torch.Tensor:
        """ Applies feathering to a Torch mask.
        :param mask_torch: Torch tensor (1, H, W) or (H, W), boolean or float, on GPU.
        :return: Feathered mask as Torch tensor (1, H, W), float, on GPU.
        """
        
        mask_float_torch = mask_torch.float()
        if mask_float_torch.ndim == 2: # HW
            mask_float_torch = mask_float_torch.unsqueeze(0) # 1HW
        if mask_float_torch.ndim == 3 and mask_float_torch.shape[0] != 1 : # CHW but C != 1
             mask_float_torch = mask_float_torch[0:1,:,:] # Take first channel

        # Add batch dimension for conv2d: (1, 1, H, W)
        mask_batch_channel = mask_float_torch.unsqueeze(0)

        gradient_x = F.conv2d(mask_batch_channel, self.sobel_x_kernel, padding=1)
        gradient_y = F.conv2d(mask_batch_channel, self.sobel_y_kernel, padding=1)

        gradient_magnitude = torch.sqrt(gradient_x**2 + gradient_y**2)
        max_grad = torch.max(gradient_magnitude)

        if max_grad < 1e-5: # Use a small epsilon to handle near-zero gradients
            return mask_float_torch # Return original 1HW float mask

        feathered_mask_batch = 1.0 - gradient_magnitude / max_grad

        return feathered_mask_batch.squeeze(0) # Return 1HW float mask


    def stitch_single_perspective(self,
                                  target_equirect_torch_cxhxw_rgb_uint8: torch.Tensor,
                                  processed_crop_torch_cxhxw_rgb_uint8: torch.Tensor,
                                  theta: float, phi: float, fov: float,
                                  is_left_eye: bool):
        """
        Stitches a single processed perspective crop back into the target equirectangular image.
        Modifies target_equirect_torch_cxhxw_rgb_uint8 in place.
        Assumes all tensors are on self.device.
        """

        # The FOV for P2E_Perspective must match the FOV of the processed_crop_torch_cxhxw_rgb_uint8.
        # This 'fov' parameter passed to stitch_single_perspective is that FOV.
        if processed_crop_torch_cxhxw_rgb_uint8 is None or processed_crop_torch_cxhxw_rgb_uint8.numel() == 0:
            print(f"stitch_single_perspective: processed_crop is None or empty. Skipping stitch for theta={theta}, phi={phi}.")
            return

        p2e_instance = P2E_Perspective(processed_crop_torch_cxhxw_rgb_uint8, FOV=fov, THETA=theta, PHI=phi)

        # 局部窗口：crop 反投影只影响全景上一块局部区域，逐脸全图计算（每脸 840 万点
        # 的网格/采样/羽化/混合）是缝合耗时根源（实测占渲染 AI 时间三分之一）。
        # 窗口取投影锥体的经纬包围盒+羽化裕量，坐标与全图 linspace 严格对齐，
        # 窗口内结果与全图计算逐像素一致。
        win = self._stitch_window(theta, phi, fov, processed_crop_torch_cxhxw_rgb_uint8.shape,
                                  self.orig_height, self.orig_width)
        if win is None:
            y0, y1, x0, x1 = 0, self.orig_height, 0, self.orig_width
        else:
            y0, y1, x0, x1 = win

        # GetEquirec returns Torch tensors (window-shaped):
        # equirect_component_torch: (C, wh, ww) RGB uint8, the processed crop warped to equirectangular space.
        # mask_torch_original_shape: (1, wh, ww) boolean, indicating valid warped pixels.
        equirect_component_torch, mask_torch_original_shape = p2e_instance.GetEquirec(
            self.orig_height, self.orig_width, window=(y0, y1, x0, x1))

        # Create eye region mask (1, wh, ww) to define the current eye's hemisphere
        eye_region_mask = torch.zeros_like(mask_torch_original_shape, dtype=torch.bool)
        half_width = self.orig_width // 2
        xs = torch.arange(x0, x1, device=self.device)
        eye_region_mask[0, :, :] = (xs < half_width).unsqueeze(0) if is_left_eye else (xs >= half_width).unsqueeze(0)

        # Apply eye region mask to the original projection mask to make it eye-specific
        eye_specific_mask_torch_original_shape = mask_torch_original_shape & eye_region_mask

        # Feather the eye-specific mask
        feathered_mask_torch_float_1hw = self._apply_feathering(eye_specific_mask_torch_original_shape) # Returns 1HW float

        # 值域融合：全程 0-255 float，省去 /255、*255 与三操作 composite；
        # torch.lerp 为单 kernel 混合。缝合成本主要由 kernel launch 数决定
        # （实测窗口化省数据时间但不省 launch，反而更慢），故以削减算子数为目标。
        target_window = target_equirect_torch_cxhxw_rgb_uint8[:, y0:y1, x0:x1]
        target_float = target_window.float()
        component_float = equirect_component_torch.float()  # 0-255

        # feathered_mask_torch_float_1hw is (1, wh, ww), can be broadcast with (C, wh, ww)
        composite_float = torch.lerp(target_float, component_float, feathered_mask_torch_float_1hw)

        # Use the eye-specific (non-feathered) mask for direct replacement areas
        # eye_specific_mask_torch_original_shape is (1, wh, ww) boolean
        # Expand to (C, wh, ww) for torch.where
        mask_for_where = eye_specific_mask_torch_original_shape.expand_as(composite_float)

        final_blended_float = torch.where(mask_for_where, composite_float, target_float)

        target_window[:] = final_blended_float.clamp_(0, 255).byte()

        # Explicitly delete intermediate tensors if memory is tight, though Python's GC + PyTorch should handle it.
        del p2e_instance, equirect_component_torch, mask_torch_original_shape
        del eye_region_mask, eye_specific_mask_torch_original_shape
        del feathered_mask_torch_float_1hw
        del target_float, component_float, composite_float, mask_for_where, final_blended_float

    def _stitch_window(self, theta: float, phi: float, fov: float, crop_shape,
                       height: int, width: int):
        """投影锥体在全景上的像素包围盒 (y0, y1, x0, x1)（含羽化裕量）。

        坐标与 GetEquirec 的 linspace 映射对齐：lon[-180,180]→x[0,W-1]，
        lat[90,-90]→y[0,H-1]。跨经度接缝（theta 靠近 ±180°，脑后位置）时
        返回 None，调用方回退全图计算。
        """
        ch, cw = crop_shape[-2], crop_shape[-1]
        w_len = np.tan(np.radians(fov / 2.0))
        h_len = np.tan(np.radians(ch / cw * fov / 2.0))
        # 投影锥体的对角角半径 + 羽化/插值裕量
        half_ang = float(np.degrees(np.arctan(np.sqrt(w_len * w_len + h_len * h_len)))) + 3.0
        lon0, lon1 = theta - half_ang, theta + half_ang
        if lon0 < -180.0 or lon1 > 180.0:
            return None
        lat0 = max(-90.0, phi - half_ang)
        lat1 = min(90.0, phi + half_ang)
        x0 = int(np.floor((lon0 + 180.0) / 360.0 * (width - 1)))
        x1 = int(np.ceil((lon1 + 180.0) / 360.0 * (width - 1))) + 1
        y0 = int(np.floor((90.0 - lat1) / 180.0 * (height - 1)))
        y1 = int(np.ceil((90.0 - lat0) / 180.0 * (height - 1))) + 1
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(width, x1), min(height, y1)
        if x1 <= x0 or y1 <= y0:
            return None
        return (y0, y1, x0, x1)
 