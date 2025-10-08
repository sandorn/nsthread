# nsthread

<div align="center">
    <strong>版本: 0.0.6</strong> | 
    <a href="https://github.com/sandorn/nsthread">GitHub</a> | 
    <strong>Python 3.13+</strong>
</div>

nsthread 是一个全面的 Python 并发编程增强库，为标准线程、进程和 Qt 线程提供了更高级的抽象和异常处理机制。作者: sandorn sandorn@live.cn

## 功能特点

- **增强的线程管理**：提供 `ThreadManager` 和 `QtThreadManager` 用于集中管理线程生命周期
- **异常安全的执行**：通过 `safe_call` 装饰器提供统一的异常捕获和日志记录
- **单例线程支持**：实现 `SingletonThread` 和 `ComposedSingletonThread` 等单例模式线程
- **Qt 集成**：提供基于 PyQt6 的线程增强实现
- **Future 模式支持**：多种线程池实现，简化异步任务处理
- **进程管理**：提供增强的进程处理能力
- **生产者-消费者模式**：实现同步和异步版本的任务处理框架
- **丰富的装饰器**：提供多种线程相关的装饰器，简化并发编程

## 安装

### 基本安装

```bash
pip install nsthread
```

### 可选依赖

如果需要使用Qt相关功能，请单独安装PyQt6：

```bash
pip install PyQt6
```

## 快速开始

### 基本线程使用

```python
from nsthread import SafeThread
import time

def worker_function():
    for i in range(5):
        print(f"Working: {i}")
        time.sleep(1)

# 创建并启动安全线程
thread = SafeThread(target=worker_function)
thread.start()
thread.join()
```

### 使用装饰器简化并发编程

```python
from nsthread import thread_safe, run_in_thread, safe_call
import time

# 确保函数线程安全
@thread_safe
def shared_resource_access(data):
    # 访问共享资源的代码
    time.sleep(0.1)  # 模拟操作
    return data * 2

# 在单独的线程中执行函数
@run_in_thread
def background_task(param):
    time.sleep(2)  # 模拟耗时操作
    return f"处理完成: {param}"

# 安全执行可能抛出异常的函数
@safe_call()
def risky_operation(value):
    if value < 0:
        raise ValueError("值不能为负数")
    return value * value

# 使用这些装饰过的函数
result1 = shared_resource_access(5)
result2 = background_task("测试")  # 立即返回，函数在后台执行
result3 = risky_operation(-1)  # 捕获异常并记录，返回默认值None
```

### 使用线程池处理批量任务

```python
from nsthread import EnhancedThreadPool
import time

def process_item(item):
    """处理单个项目的函数"""
    time.sleep(0.5)  # 模拟处理时间
    return item * item

# 创建线程池
pool = EnhancedThreadPool(max_workers=4)

# 提交多个任务
results = []
for i in range(10):
    future = pool.submit(process_item, i)
    results.append(future)

# 获取所有结果
final_results = [future.result() for future in results]
print(f"处理结果: {final_results}")

# 关闭线程池
pool.shutdown()
```

### 生产者-消费者模式示例

```python
from nsthread import Production
import time
import random

def producer():
    """生产者函数，生成任务项"""
    time.sleep(random.uniform(0.1, 0.5))  # 模拟生产时间
    return random.randint(1, 100)

def consumer(item):
    """消费者函数，处理任务项"""
    time.sleep(random.uniform(0.2, 0.7))  # 模拟消费时间
    return item * 2

# 创建生产系统
production = Production(queue_size=5)

# 启动系统，2个生产者，3个消费者
production.start(num_producers=2, num_consumers=3, producer_fn=producer, consumer_fn=consumer)

# 运行一段时间
print("生产系统运行中...")
time.sleep(5)

# 等待所有任务处理完成
print("等待所有任务处理完成...")
production.wait_until_done(timeout=10)

# 获取所有结果
results = production.get_result_list()
print(f"处理结果数量: {len(results)}")

# 关闭系统
production.shutdown()
print("生产系统已关闭")

## 核心模块

### exception.py
提供 `safe_call` 装饰器，用于捕获和处理函数执行过程中的异常，确保异常被妥善记录而不导致程序崩溃。

### thread.py
提供标准 Python 线程的增强实现，包括 `ThreadBase`、`SafeThread`、`ThreadManager` 等类。

### qt_thread.py
提供基于 PyQt6 的线程增强实现，包括 `QtThreadBase`、`QtSafeThread`、`QtThreadManager` 等类。

### singleton.py
提供单例模式的实现，用于创建单例线程。

### futures.py
提供 Future 模式的实现，简化异步任务处理。

### process.py
提供增强的进程处理能力。

### wraps.py
提供功能增强的装饰器集合。

## 使用示例

### 基本线程使用

```python
from nsthread import SafeThread
import time

def worker_function():
    for i in range(5):
        print(f"Working: {i}")
        time.sleep(1)

# 创建并启动安全线程
thread = SafeThread(target=worker_function)
thread.start()
thread.join()
```

### 使用 ThreadManager 管理多个线程

```python
from nsthread import ThreadManager
import time

def task(name, count):
    for i in range(count):
        print(f"Task {name}: {i}")
        time.sleep(0.5)
    return f"Task {name} completed"

# 创建线程管理器
manager = ThreadManager()

# 添加并启动多个线程
manager.create_thread(target=task, args=("A", 3))
manager.create_thread(target=task, args=("B", 5))

# 等待所有线程完成
manager.wait_all_completed()

# 获取所有线程的结果
results = manager.get_all_result()
print(f"All results: {results}")
```

### 使用 safe_call 装饰器

```python
from nsthread import safe_call

def might_raise_error(value):
    if value < 0:
        raise ValueError("Value cannot be negative")
    return value * 2

# 使用装饰器包装函数
@safe_call()
def safe_function(value):
    return might_raise_error(value)

# 安全地调用可能抛出异常的函数
safe_function(10)  # 返回 20
safe_function(-1)  # 记录异常但不会导致程序崩溃
```

### Qt 线程使用

```python
from nsthread import QtSafeThread
from PyQt6.QtWidgets import QApplication
import sys
import time

def qt_worker():
    for i in range(10):
        print(f"Qt thread working: {i}")
        time.sleep(0.5)
    return "Qt thread completed"

app = QApplication(sys.argv)

# 创建并启动 Qt 安全线程
qt_thread = QtSafeThread(target=qt_worker)
qt_thread.result_ready.connect(lambda result: print(f"Result: {result}"))
qt_thread.start()

# 运行 Qt 应用程序主循环
sys.exit(app.exec())
```

## 使用场景

- **简单并发任务**: 使用 ThreadBase 或 SafeThread
- **批量任务处理**: 使用 BaseThreadPool 或 EnhancedThreadPool
- **动态资源管理**: 使用 DynamicThreadPool 或 ThreadPoolManager
- **跨进程并行**: 使用 CustomProcess 或 run_custom_process
- **UI响应式应用**: 使用 QtThreadBase 或 QtSafeThread
- **复杂任务流**: 使用 Production 或 AsyncProduction
- **异步函数执行**: 使用 AsyncFunction
- **线程安全保证**: 使用 thread_safe 装饰器
- **单例线程**: 使用 SingletonThread 或 SingletonQtThread

## API 参考

### 核心装饰器

#### safe_call
```python
def safe_call(log_level: int = logging.ERROR, default_return: Any = None):
    """捕获函数执行过程中的异常并记录日志
    
    参数:
        log_level: 日志记录级别
        default_return: 发生异常时的默认返回值
    """
```

#### thread_safe
```python
def thread_safe(func: Callable[..., T]) -> Callable[..., T]:
    """确保函数在多线程环境下的安全性
    
    参数:
        func: 要保护的目标函数
    
    返回:
        线程安全的函数包装器
    """
```

#### run_in_thread
```python
def run_in_thread(func: Callable[..., T]) -> Callable[..., T]:
    """在单独的线程中执行函数
    
    参数:
        func: 要在新线程中执行的目标函数
    
    返回:
        异步执行的函数包装器
    """
```

### 线程基础类

#### ThreadBase
```python
class ThreadBase(threading.Thread):
    """基础线程类，提供线程生命周期管理和结果存储功能
    
    属性:
        result: 线程执行的结果
        error: 线程执行过程中的异常（如果有）
        is_stopped: 线程是否已停止
    
    方法:
        stop(): 安全地停止线程
        join(timeout=None): 等待线程完成
        get_result(block=True, timeout=None): 获取线程执行结果
    """
```

#### SafeThread
```python
class SafeThread(ThreadBase):
    """继承自 ThreadBase，提供额外的异常处理机制
    
    特性:
        - 自动捕获并记录线程执行过程中的异常
        - 提供更安全的线程停止机制
        - 支持结果获取和超时控制
    """
```

### 线程管理器

#### ThreadManager
```python
class ThreadManager(SingletonMixin):
    """线程管理器，用于集中管理多个线程的创建、启动、停止和结果获取
    
    类方法:
        create_thread(target, *args, **kwargs): 创建并启动一个新线程
        create_safe_thread(target, *args, **kwargs): 创建并启动一个安全线程
        add_thread(thread): 添加一个已创建的线程
        stop_all(wait=True): 停止所有管理的线程
        wait_all_completed(timeout=None): 等待所有线程完成
        get_all_result(): 获取所有线程的执行结果
        get_active_count(): 获取当前活跃的线程数量
    """
```

### 线程池

#### BaseThreadPool
```python
class BaseThreadPool:
    """基础线程池实现
    
    参数:
        max_workers: 最大工作线程数
        name_prefix: 线程名称前缀
    
    方法:
        submit(func, *args, **kwargs): 提交任务到线程池
        shutdown(wait=True): 关闭线程池
        get_workers_count(): 获取当前工作线程数量
    """
```

#### EnhancedThreadPool
```python
class EnhancedThreadPool(BaseThreadPool):
    """增强型线程池，提供更多高级功能
    
    特性:
        - 任务优先级支持
        - 任务取消功能
        - 动态调整线程池大小
        - 任务完成回调
    """
```

#### AsyncFunction
```python
class AsyncFunction:
    """函数异步执行包装器
    
    参数:
        fn: 要执行的目标函数
        *args: 传递给目标函数的参数
        **kwargs: 传递给目标函数的关键字参数
        max_workers: 可选,指定线程池最大工作线程数
    
    属性:
        result: 异步执行的结果
    """
```

### 单例线程

#### SingletonThread
```python
class SingletonThread(SingletonMixin, SafeThread):
    """单例线程类，确保同一目标函数只有一个线程实例
    
    特性:
        - 单例模式保证唯一性
        - 自动线程管理
        - 安全停止机制
    """
```

### Qt 线程

#### QtThreadBase
```python
class QtThreadBase(QThread):
    """基于QThread的增强型线程基类
    
    信号:
        finished_signal: 线程完成时发射，携带执行结果
        error_signal: 线程发生错误时发射，携带异常信息
    
    方法:
        stop(): 安全停止线程
        get_result(): 获取线程执行结果
    """
```

#### QtSafeThread
```python
class QtSafeThread(QtThreadBase):
    """基于QThread的安全线程类
    
    特性:
        - 自动异常捕获和信号发射
        - 安全的资源管理
        - 结果获取机制
    """
```

### 生产者-消费者模式

#### Production
```python
class Production:
    """同步多线程生产者-消费者模式实现
    
    参数:
        queue_size: 任务队列的最大容量
    
    方法:
        start(num_producers, num_consumers, producer_fn, consumer_fn): 启动生产系统
        shutdown(): 关闭生产系统
        wait_until_done(timeout=None): 等待所有任务处理完成
        get_result(): 获取一个处理结果
        get_result_list(): 获取所有处理结果
    """
```

#### AsyncProduction
```python
class AsyncProduction:
    """异步协程生产者-消费者模式实现
    
    参数:
        queue_size: 异步任务队列的最大容量
    
    方法:
        start(num_producers, num_consumers, producer_fn, consumer_fn): 启动异步生产系统
        shutdown(): 关闭异步生产系统
        wait_until_done(timeout=None): 等待所有任务处理完成
    """
```

### 进程管理

#### CustomProcess
```python
class CustomProcess(multiprocessing.Process):
    """自定义进程类，提供增强的进程管理功能
    
    特性:
        - 结果返回机制
        - 异常处理
        - 优雅的进程终止
    """
```

#### run_custom_process
```python
def run_custom_process(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在新进程中执行函数并返回结果
    
    参数:
        func: 要在新进程中执行的函数
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数
    
    返回:
        函数执行的结果
    """
```

## 测试

项目包含完整的测试套件，使用以下命令运行测试：

```bash
pytest
```

## 开发工具

项目使用以下工具进行代码质量保证：

- **Ruff**: 用于代码风格检查和格式化
- **basedpyright**: 用于静态类型检查
- **mypy**: 可选的静态类型检查器

## 贡献指南

1. Fork 项目仓库
2. 创建功能分支
3. 提交代码更改
4. 运行测试确保代码质量
5. 提交 Pull Request

## 许可证

本项目采用 MIT 许可证。