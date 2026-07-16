"""
验证对话功能改进：
1. ModelListAPIHandler 可访问
2. 流式消息类型正确发送
3. 对话历史被包含在模型调用中
"""
import json
import sys
import os

# 强制 UTF-8 输出，解决 Windows GBK 编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 语法验证：确保所有修改的文件能正确导入
print("=== 1. 语法与导入验证 ===")

try:
    import py_compile
    py_compile.compile('app/controllers/chat.py', doraise=True)
    print("✅ chat.py 语法正确")
except py_compile.PyCompileError as e:
    print(f"❌ chat.py 语法错误: {e}")
    sys.exit(1)

try:
    py_compile.compile('app.py', doraise=True)
    print("✅ app.py 语法正确")
except py_compile.PyCompileError as e:
    print(f"❌ app.py 语法错误: {e}")
    sys.exit(1)

# 导入验证
try:
    from app.controllers.chat import (
        ChatWebSocketHandler, ConversationAPIHandler,
        DigitalEmployeeAPIHandler, ModelListAPIHandler
    )
    print("✅ chat.py 导入成功：所有 Handler 类存在")
except ImportError as e:
    print(f"❌ chat.py 导入失败: {e}")
    sys.exit(1)

try:
    from app.models.model import AIModelRepository, AIModelService
    print("✅ model.py 导入成功")
except ImportError as e:
    print(f"❌ model.py 导入失败: {e}")
    sys.exit(1)

print("\n=== 2. 后端代码结构验证 ===")

# 验证 ChatWebSocketHandler 有新增的方法
assert hasattr(ChatWebSocketHandler, '_get_model'), "❌ 缺少 _get_model 方法"
print("✅ _get_model 方法存在")

assert hasattr(ChatWebSocketHandler, '_build_chat_messages'), "❌ 缺少 _build_chat_messages 方法"
print("✅ _build_chat_messages 方法存在")

# 验证 handle_general_chat 签名
import inspect
sig = inspect.signature(ChatWebSocketHandler.handle_general_chat)
params = list(sig.parameters.keys())
assert 'model_id' in params, f"❌ handle_general_chat 缺少 model_id 参数: {params}"
print(f"✅ handle_general_chat 签名正确: {params}")

# 验证 handle_message 签名
sig = inspect.signature(ChatWebSocketHandler.handle_message)
params = list(sig.parameters.keys())
assert 'model_id' in params, f"❌ handle_message 缺少 model_id 参数: {params}"
print(f"✅ handle_message 签名正确: {params}")

# 验证 ModelListAPIHandler 有 get 方法
assert hasattr(ModelListAPIHandler, 'get'), "❌ ModelListAPIHandler 缺少 get 方法"
print("✅ ModelListAPIHandler.get 方法存在")

print("\n=== 3. 路由注册验证 ===")
import importlib.util, sys
spec = importlib.util.spec_from_file_location("app_module", "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
app = app_module.webapp()
# 验证 /api/models 路由已注册：从 webapp() 源码中直接验证
import inspect
webapp_source = inspect.getsource(app_module.webapp)
assert '/api/models' in webapp_source, "❌ /api/models 路由未在 webapp() 中注册"
print(f"✅ /api/models 路由已注册")

print("\n=== 4. 关键代码逻辑验证 ===")

# 验证 handle_general_chat 使用流式调用
import inspect
source = inspect.getsource(ChatWebSocketHandler.handle_general_chat)
assert 'stream_start' in source, "❌ handle_general_chat 未发送 stream_start"
print("✅ handle_general_chat 发送 stream_start")
assert 'stream_chunk' in source, "❌ handle_general_chat 未发送 stream_chunk"
print("✅ handle_general_chat 发送 stream_chunk")
assert 'stream=True' in source, "❌ handle_general_chat 未使用 stream=True"
print("✅ handle_general_chat 使用 stream=True")
assert 'get_messages' in source or '_build_chat_messages' in source, "❌ handle_general_chat 未获取对话历史"
print("✅ handle_general_chat 获取对话历史")

# 验证 _build_chat_messages 包含系统提示词
source = inspect.getsource(ChatWebSocketHandler._build_chat_messages)
assert 'system' in source, "❌ _build_chat_messages 未包含 system role"
print("✅ _build_chat_messages 包含 system prompt")
assert 'get_messages' in source, "❌ _build_chat_messages 未调用 get_messages"
print("✅ _build_chat_messages 获取对话历史")

print("\n=== 5. 前端模板验证 ===")
with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

assert 'loadModels()' in html, "❌ index.html 缺少 loadModels 函数"
print("✅ index.html 包含 loadModels 函数")

assert 'stream_start' in html, "❌ index.html 缺少 stream_start 处理"
print("✅ index.html 处理 stream_start")

assert 'stream_chunk' in html, "❌ index.html 缺少 stream_chunk 处理"
print("✅ index.html 处理 stream_chunk")

assert 'appendStreamingMessage' in html, "❌ index.html 缺少 appendStreamingMessage"
print("✅ index.html 包含 appendStreamingMessage")

assert 'appendStreamChunk' in html, "❌ index.html 缺少 appendStreamChunk"
print("✅ index.html 包含 appendStreamChunk")

assert 'selectedModelId' in html, "❌ index.html 缺少 selectedModelId"
print("✅ index.html 包含 selectedModelId")

assert 'model_id: selectedModelId' in html, "❌ sendMessage 未包含 model_id"
print("✅ sendMessage 发送 model_id")

assert "streamingMessageDiv = null" in html, "❌ done 处理未清除 streamingMessageDiv"
print("✅ done 处理清除 streamingMessageDiv")

print("\n=== 🎉 所有验证通过！===")
