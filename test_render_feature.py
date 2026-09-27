"""
测试渲染功能的脚本
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试导入是否正常"""
    try:
        from app.processors.render_thread import RenderThread
        print("[OK] RenderThread 导入成功")
    except ImportError as e:
        print(f"[FAIL] RenderThread 导入失败: {e}")
        print("提示: 请在 conda 环境 visomaster 中运行测试")
        return False
    
    try:
        from app.ui.widgets.actions import video_control_actions
        print("[OK] video_control_actions 导入成功")
    except ImportError as e:
        print(f"[FAIL] video_control_actions 导入失败: {e}")
        return False
    
    return True

def test_render_thread_class():
    """测试 RenderThread 类结构"""
    try:
        from app.processors.render_thread import RenderThread
        from PySide6.QtCore import QThread, Signal
        
        # 检查是否继承自 QThread
        if not issubclass(RenderThread, QThread):
            print("[FAIL] RenderThread 未继承自 QThread")
            return False
        print("[OK] RenderThread 正确继承自 QThread")
        
        # 检查信号定义
        if not hasattr(RenderThread, 'progress_signal'):
            print("[FAIL] RenderThread 缺少 progress_signal")
            return False
        print("[OK] RenderThread 包含 progress_signal")
        
        if not hasattr(RenderThread, 'finished_signal'):
            print("[FAIL] RenderThread 缺少 finished_signal")
            return False
        print("[OK] RenderThread 包含 finished_signal")
        
        if not hasattr(RenderThread, 'error_signal'):
            print("[FAIL] RenderThread 缺少 error_signal")
            return False
        print("[OK] RenderThread 包含 error_signal")
        
        # 检查方法定义
        if not hasattr(RenderThread, 'run'):
            print("[FAIL] RenderThread 缺少 run 方法")
            return False
        print("[OK] RenderThread 包含 run 方法")
        
        if not hasattr(RenderThread, 'cancel'):
            print("[FAIL] RenderThread 缺少 cancel 方法")
            return False
        print("[OK] RenderThread 包含 cancel 方法")
        
        return True
    except Exception as e:
        print(f"[FAIL] 测试 RenderThread 类时出错: {e}")
        return False

def test_video_control_actions():
    """测试 video_control_actions 函数"""
    try:
        from app.ui.widgets.actions import video_control_actions
        
        # 检查渲染控制函数
        if not hasattr(video_control_actions, 'set_render_start_point'):
            print("[FAIL] 缺少 set_render_start_point 函数")
            return False
        print("[OK] 包含 set_render_start_point 函数")
        
        if not hasattr(video_control_actions, 'set_render_end_point'):
            print("[FAIL] 缺少 set_render_end_point 函数")
            return False
        print("[OK] 包含 set_render_end_point 函数")
        
        if not hasattr(video_control_actions, 'start_render_and_save'):
            print("[FAIL] 缺少 start_render_and_save 函数")
            return False
        print("[OK] 包含 start_render_and_save 函数")
        
        if not hasattr(video_control_actions, 'reset_render_range'):
            print("[FAIL] 缺少 reset_render_range 函数")
            return False
        print("[OK] 包含 reset_render_range 函数")
        
        return True
    except Exception as e:
        print(f"[FAIL] 测试 video_control_actions 时出错: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("渲染功能测试")
    print("=" * 50)
    
    all_passed = True
    
    print("\n1. 测试导入...")
    if not test_imports():
        all_passed = False
    
    print("\n2. 测试 RenderThread 类...")
    if not test_render_thread_class():
        all_passed = False
    
    print("\n3. 测试 video_control_actions 函数...")
    if not test_video_control_actions():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[OK] 所有测试通过！")
    else:
        print("[FAIL] 部分测试失败")
    print("=" * 50)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
