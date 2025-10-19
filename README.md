<div align="center">
    <strong>版本: 0.0.7</strong> | 
    <a href="https://github.com/sandorn/xtthread">GitHub</a> | 
    <strong>Python 3.13+</strong>
</div>

# xtthread

xtthread 是一个全面的 Python 并发编程增强库，为标准线程、进程和 Qt 线程提供了更高级的抽象和异常处理机制。作者: sandorn sandorn@live.cn

## 功能特点

-   **增强的线程管理**：提供 `ThreadManager` 和 `QtThreadManager` 用于集中管理线程生命周期
-   **异常安全的执行**：通过 `safe_call` 装饰器提供统一的异常捕获和日志记录
-   **单例线程支持**：实现 `SingletonThread` 和 `ComposedSingletonThread` 等单例模式线程
-   **Qt 集成**：提供基于 PyQt6 的线程增强实现
-   **Future 模式支持**：多种线程池实现，简化异步任务处理
-   **进程管理**：提供增强的进程处理能力
-   **生产者-消费者模式**：实现同步和异步版本的任务处理框架
-   **丰富的装饰器**：提供多种线程相关的装饰器，简化并发编程

## 安装

### 基本安装

```bash
pip install xtthread
```

### 可选依赖

如果需要使用 Qt 相关功能，请单独安装 PyQt6：

```bash
pip install PyQt6
```

## 快速开始

### 1. 基本线程使用

```python
from xtthread import ThreadBase

# 创建线程并启动
def my_task(name):
    import time
    time.sleep(1)  # 模拟耗时操作
    return f"Hello, {name}!"

thread = ThreadBase(target=my_task, args=("World",))
thread.start()

# 获取线程执行结果
result = thread.get_result(timeout=2)
print(result)  # 输出: Hello, World!
```

### 2. 使用装饰器简化并发编程

```python
from xtthread import run_in_thread, safe_call
import time

# 在单独线程中执行函数
@run_in_thread
@safe_call
def process_data(data):
    time.sleep(1)  # 模拟处理时间
    return data * 2

# 调用函数（异步执行）
thread = process_data(10)

# 主线程可以做其他事情
print("等待处理结果...")

# 获取结果
result = thread.get_result()
print(f"处理结果: {result}")
```

### 3. 使用线程池处理批量任务

```python
from xtthread import EnhancedThreadPool
import time

# 创建线程池（最多4个工作线程）
with EnhancedThreadPool(max_workers=4) as pool:
    # 提交多个任务
    tasks = [pool.submit(time.sleep, i * 0.5) for i in range(1, 6)]

    # 等待所有任务完成并获取结果
    results = pool.wait_all_completed()
    print(f"任务完成数量: {len(results)}")
```

### 4. 生产者-消费者模式

```python
from xtthread import Production
import time
import random

# 创建生产者-消费者系统
production = Production(queue_size=10)

# 定义生产者函数
def producer():
    for i in range(5):
        task_data = random.randint(1, 100)
        production.add_task(task_data)
        print(f"生产者添加任务: {task_data}")
        time.sleep(0.5)

# 定义消费者函数
def consumer(task_data):
    print(f"消费者处理任务: {task_data}")
    time.sleep(1)  # 模拟处理时间
    return task_data * 2

# 添加生产者和消费者
production.add_producer(producer)
production.add_consumer(consumer, num_workers=2)

# 启动系统
production.start()

# 等待所有任务完成
production.wait_completed()

# 获取处理结果
results = production.get_results()
print(f"所有结果: {results}")
```

## 核心模块详解

### 1. 异常处理模块 (`exception.py`)

提供统一的异常捕获和处理机制，确保并发任务中的异常被正确记录和处理。

#### handle_exception

```python
"""统一的异常处理函数，提供完整的异常捕获、记录和处理机制

参数:
    exc: 异常对象
    re_raise: 是否重新抛出异常，默认False
    handler: 异常处理函数，默认None
    default_return: 默认返回值
    log_traceback: 是否记录完整堆栈信息，默认True
    custom_message: 自定义错误提示信息，默认None

返回:
    如果re_raise=True，重新抛出异常；否则返回default_return
"""
```

#### safe_call

```python
"""捕获函数执行过程中的异常并记录日志

参数:
    func: 要执行的目标函数
    re_raise: 是否重新抛出异常，默认False
    handler: 异常处理函数，默认None
    default_return: 默认返回值

返回:
    包装后的函数
"""
```

### 2. 线程基础模块 (`thread.py`)

提供增强型线程基类和线程管理功能。

#### ThreadBase

```python
"""增强型线程基类，提供结果获取、安全停止和资源清理功能

特性:
    支持结果获取、超时控制、安全停止和资源自动清理
    可作为上下文管理器使用
"""
```

#### SafeThread

```python
"""继承自 ThreadBase，提供额外的异常处理机制

特性:
    内置异常捕获和重试机制
    确保线程即使在出错情况下也能正确结束
"""
```

#### ThreadManager

```python
"""线程管理器，用于集中管理多个线程的创建、启动、停止和结果获取

类方法:
    create_thread: 创建并返回线程实例
    start_all: 启动所有创建的线程
    wait_all_completed: 等待所有线程完成并返回结果列表
    stop_all: 安全停止所有线程
"""
```

### 3. 线程池模块 (`futures.py`)

提供多种线程池实现，满足不同的并发需求。

#### BaseThreadRunner

```python
"""极简线程池实现，使用信号量控制并发线程数量

参数:
    max_workers: 最大工作线程数
    name_prefix: 线程名称前缀

方法:
    submit: 提交任务到线程池
    wait_all_completed: 等待所有任务完成并返回结果列表
"""
```

#### EnhancedThreadPool

```python
"""增强型线程池，扩展标准ThreadPoolExecutor，提供结果收集和异常处理

特性:
    自动收集任务结果
    支持超时控制
    完整的异常捕获和处理
    支持上下文管理器语法
"""
```

### 4. 进程管理模块 (`process.py`)

提供增强的进程管理功能，支持跨进程并行计算。

#### ProcessBase

```python
"""增强型进程基类，提供结果获取、安全停止和资源清理功能

特性:
    支持结果获取、超时控制、安全停止和资源自动清理
    可作为上下文管理器使用
"""
```

#### CustomProcess

```python
"""自定义进程类，提供任务分片和结果收集功能

参数:
    target: 目标函数
    chunk_size: 任务分片大小
    max_workers: 最大工作进程数

方法:
    add_task: 添加单个任务
    add_tasks: 添加多个任务
    start: 启动进程
    wait_completed: 等待所有任务完成
"""
```

### 5. 生产者-消费者模式模块 (`production.py`)

提供同步和异步版本的生产者-消费者模式实现。

#### Production

```python
"""同步多线程生产者-消费者模式实现

参数:
    queue_size: 任务队列的最大容量
    max_workers: 最大工作线程数

方法:
    add_producer: 添加生产者函数
    add_consumer: 添加消费者函数
    add_task: 直接添加任务到队列
    start: 启动所有生产者和消费者
    wait_completed: 等待所有任务完成
    get_results: 获取所有处理结果
"""
```

#### AsyncProduction

```python
"""异步协程生产者-消费者模式实现

参数:
    queue_size: 异步任务队列的最大容量

方法:
    add_producer: 添加异步生产者协程
    add_consumer: 添加异步消费者协程
    add_task: 直接添加任务到队列
    start: 启动所有生产者和消费者
    wait_completed: 等待所有任务完成
    get_results: 获取所有处理结果
"""
```

### 6. PyQt 线程增强模块 (`qthread.py`)

提供基于 PyQt6 的线程增强功能，适用于 GUI 应用程序。

#### QtThreadBase

```python
"""基于QThread的增强型线程基类

信号:
    finished_signal: 线程完成时发射，携带执行结果
    error_signal: 线程发生错误时发射，携带异常信息

特性:
    支持结果获取、超时控制、安全停止
    可作为上下文管理器使用
"""
```

#### QtThreadManager

```python
"""Qt线程管理器，用于集中管理多个Qt线程

类方法:
    create_thread: 创建并返回Qt线程实例
    start_all: 启动所有创建的线程
    wait_all_completed: 等待所有线程完成并返回结果列表
    stop_all: 安全停止所有线程
"""
```

### 7. 装饰器集合 (`wraps.py`)

提供多种线程相关的装饰器，简化并发编程。

#### thread_safe

```python
"""确保函数在多线程环境下的安全性

参数:
    func: 要保护的目标函数

返回:
    线程安全的包装函数
"""
```

#### run_in_thread

```python
"""在单独的线程中执行函数

参数:
    func: 要在新线程中执行的目标函数
    daemon: 是否为守护线程，默认True

返回:
    包装后的函数，调用后返回线程实例
"""
```

#### run_in_qtthread

```python
"""在QThread中执行函数

参数:
    func: 要在QThread中执行的目标函数

返回:
    包装后的函数，调用后返回Qt线程实例
"""
```

## 单例线程支持

xtthread 提供了多种单例模式线程实现，确保同一目标函数只有一个线程实例运行：

-   `SingletonThread`: 确保同一目标函数只有一个线程实例
-   `ComposedSingletonThread`: 使用组合而非继承实现的单例线程
-   `SingletonQtThread`: 基于 QThread 的单例线程
-   `ComposedSingletonQtThread`: 基于组合模式的 Qt 单例线程

## 使用场景

xtthread 适用于以下各种并发编程场景：

-   **简单并发任务**: 使用 ThreadBase 或 SafeThread
-   **批量任务处理**: 使用 BaseThreadPool 或 EnhancedThreadPool
-   **动态资源管理**: 使用 DynamicThreadPool 或 ThreadPoolManager
-   **跨进程并行**: 使用 CustomProcess 或 run_custom_process
-   **UI 响应式应用**: 使用 QtThreadBase 或 QtSafeThread
-   **复杂任务流**: 使用 Production 或 AsyncProduction
-   **异步函数执行**: 使用 AsyncFunction
-   **线程安全保证**: 使用 thread_safe 装饰器
-   **单例线程**: 使用 SingletonThread 或 SingletonQtThread

## 开发工具

本项目使用以下工具确保代码质量：

-   **Ruff**: 用于代码风格检查和格式化
-   **basedpyright**: 用于静态类型检查
-   **mypy**: 可选的静态类型检查器

## 许可证

本项目采用 MIT 许可证。
