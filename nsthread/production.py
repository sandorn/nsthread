# !/usr/bin/env python
"""
==============================================================
Description  : 生产者-消费者模式实现 - 提供同步和异步版本的任务处理框架
Develop      : VSCode
Author       : sandorn sandorn@live.cn
LastEditTime : 2025-09-06 21:00:00
Github       : https://github.com/sandorn/nsthread

本模块提供以下核心功能：
- Production：同步多线程生产者-消费者模式实现
- AsyncProduction：异步协程生产者-消费者模式实现
- SyncProductionManager：同步生产消费系统管理器（简化外部调用）
- AsyncProductionManager：异步生产消费系统管理器（简化外部调用）

主要特性：
- 支持动态添加多个生产者和消费者
- 任务队列管理,自动处理队列满/空的情况
- 完整的异常捕获和处理机制
- 优雅的系统关闭流程
- 结果收集和管理功能
- 适用于IO密集型和计算密集型任务的并行处理
- 内置运行状态统计功能
==============================================================
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

from xtlog import mylog


class Production:
    """
    同步多线程生产者-消费者模式实现

    提供一个基于多线程的任务处理框架,支持动态添加多个生产者和消费者线程,
    适用于需要高效处理批量任务的场景。内置统计功能，可监控系统运行状态。

    Args:
        queue_size: 任务队列的最大容量,默认为10

    Example:
        >>> def producer():
        ...     return random.randint(1, 100)
        >>> def consumer(item):
        ...     return item * 2
        >>> production = Production(queue_size=5)
        >>> production.add_producer(producer)
        >>> production.add_consumer(consumer)
        >>> time.sleep(2)
        >>> results = production.shutdown()
    """

    def __init__(self, queue_size: int = 10):
        """初始化生产系统

        Args:
            queue_size: 任务队列的最大容量,默认为10
        """
        self.queue = queue.Queue(maxsize=queue_size)
        self.res_queue = queue.Queue()
        self.running = threading.Event()
        self.producers: list[threading.Thread] = []
        self.consumers: list[threading.Thread] = []
        self.tasks = 0
        self.error_callback: Callable | None = None

        # 统计信息
        self.produced_count = 0  # 已生产的任务数
        self.consumed_count = 0  # 已消费的任务数
        self.error_count = 0  # 处理失败的任务数
        self.start_time = time.time()  # 系统启动时间
        self._stats_lock = threading.Lock()  # 保护统计数据的锁

    def add_producer(self, producer_fn: Callable[[], Any], name: str | None = None) -> None:
        """添加生产者线程

        Args:
            producer_fn: 生产者函数,无参数,返回待处理的任务项
            name: 线程名称,默认为自动生成的名称

        Example:
            >>> production.add_producer(lambda: random.randint(1, 100), 'NumberProducer')
        """
        producer = threading.Thread(
            target=self._producer_wrapper,
            args=(producer_fn,),
            name=name or f'Producer-{len(self.producers)}',
            daemon=True,  # 设置为守护线程,避免阻止程序退出
        )
        self.producers.append(producer)
        producer.start()

    def add_consumer(self, consumer_fn: Callable[[Any], Any], name: str | None = None) -> None:
        """添加消费者线程

        Args:
            consumer_fn: 消费者函数,接收任务项参数,返回处理结果
            name: 线程名称,默认为自动生成的名称

        Example:
            >>> production.add_consumer(lambda x: x * 2, 'DoubleProcessor')
        """
        consumer = threading.Thread(
            target=self._consumer_wrapper,
            args=(consumer_fn,),
            name=name or f'Consumer-{len(self.consumers)}',
            daemon=True,  # 设置为守护线程,避免阻止程序退出
        )
        self.consumers.append(consumer)
        consumer.start()

    def _producer_wrapper(self, producer_fn: Callable[[], Any]) -> None:
        """生产者包装函数,处理异常和停止信号

        持续调用生产者函数生成任务项,并将其放入任务队列中,直到收到停止信号或发生异常。
        同时收集生产统计数据。

        Args:
            producer_fn: 生产者函数,无参数,返回待处理的任务项
        """
        while not self.running.is_set():  # 守护生产循环
            try:
                item = producer_fn()
                self.queue.put(item, timeout=1)  # 设置超时,定期检查停止信号
                with self._stats_lock:
                    self.produced_count += 1
                    self.tasks += 1
            except queue.Full:
                # 优化：避免CPU空转,增加短暂休眠
                time.sleep(0.01)  # 短暂休眠10ms,减轻CPU负载
                continue
            except Exception as e:
                mylog.debug(f'生产者发生错误: {e}')
                break

    def _consumer_wrapper(self, consumer_fn: Callable[[Any], Any]) -> None:
        """消费者包装函数,处理异常和停止信号,确保消费完队列后退出

        持续从任务队列中获取任务项并调用消费者函数处理,直到队列清空且收到停止信号。
        同时收集消费统计数据。

        Args:
            consumer_fn: 消费者函数,接收任务项参数,返回处理结果
        """
        while not (self.running.is_set() and self.queue.empty()):
            try:
                item = self.queue.get(timeout=1)  # 设置超时,定期检查停止信号
                try:
                    res = consumer_fn(item)
                    self.res_queue.put(res)
                    with self._stats_lock:
                        self.consumed_count += 1
                        self.tasks -= 1
                except Exception as e:
                    with self._stats_lock:
                        self.error_count += 1
                    if self.error_callback:
                        self.error_callback(e, item)
                    else:
                        mylog.debug(f'消费失败: {e}')
                finally:
                    self.queue.task_done()  # 标记任务完成
            except queue.Empty:
                # 优化：避免CPU空转,增加短暂休眠
                time.sleep(0.01)  # 短暂休眠10ms,减轻CPU负载
                continue

    def set_error_callback(self, callback: Callable[[Exception, Any], None]) -> None:
        """设置错误处理回调函数

        Args:
            callback: 接收异常对象和失败的任务项作为参数的回调函数

        Example:
            >>> production.set_error_callback(lambda e, item: mylog.debug(f'处理{item}时出错: {e}'))
        """
        self.error_callback = callback

    def shutdown(self, timeout: float | None = 1) -> list[Any]:
        """停止所有生产者和消费者,等待队列消费完毕

        Args:
            timeout: 等待超时时间（秒），None表示无限等待

        Returns:
            list[Any]: 所有处理结果的列表

        Example:
            >>> results = production.shutdown()
            >>> mylog.debug(f'共处理了{len(results)}个任务')
        """
        self.running.set()  # 发送停止信号,生产者停止生产

        # 先等待队列清空，再等待线程结束
        start_time = time.time()
        while not self.queue.empty():
            if timeout is not None and time.time() - start_time > timeout:
                # 优化：添加超时警告日志
                mylog.debug(f'队列清空超时,仍有{self.queue.qsize()}个任务未处理')
                break
            time.sleep(0.1)  # 短暂休眠避免CPU占用过高

        # 等待线程结束
        for thread in self.producers:
            thread.join(timeout=0.5)
        for thread in self.consumers:
            thread.join(timeout=0.5)

        # 收集结果并清空队列
        res_list = list(self.res_queue.queue)
        self.res_queue.queue.clear()
        mylog.debug('生产系统已关闭')
        return res_list

    def get_result(self) -> Any:
        """从结果队列中获取一个结果（阻塞直到有结果可用）

        Returns:
            Any: 消费者处理后的结果

        Example:
            >>> result = production.get_result()
        """
        return self.res_queue.get()

    def get_result_list(self) -> list[Any]:
        """获取当前所有的处理结果列表

        Returns:
            list[Any]: 所有已处理完成的结果列表

        Example:
            >>> current_results = production.get_result_list()
        """
        return list(self.res_queue.queue)

    def get_task_count(self) -> int:
        """获取当前待处理的任务数量

        Returns:
            int: 待处理的任务数量

        Example:
            >>> if production.get_task_count() > 0:
            ...     mylog.debug(f'还有{production.get_task_count()}个任务未完成')
        """
        return self.tasks

    def get_stats(self) -> dict:
        """获取系统运行统计信息

        Returns:
            dict: 包含系统运行指标的字典
        """
        with self._stats_lock:
            return {
                'produced_count': self.produced_count,
                'consumed_count': self.consumed_count,
                'error_count': self.error_count,
                'pending_tasks': self.tasks,
                'queue_size': self.queue.qsize(),
                'runtime_seconds': time.time() - self.start_time,
                'producer_count': len(self.producers),
                'consumer_count': len(self.consumers),
            }


class AsyncProduction:
    """
    异步协程生产者-消费者模式实现

    提供一个基于asyncio的异步任务处理框架,使用协程而非线程来实现生产者-消费者模式,
    特别适合IO密集型任务的高效处理。

    Args:
        queue_size: 异步任务队列的最大容量,默认为10

    Example:
        >>> async def producer():
        ...     await asyncio.sleep(0.1)
        ...     return random.randint(1, 100)
        >>> async def consumer(item):
        ...     await asyncio.sleep(0.2)
        ...     return item * 2
        >>> async def main():
        ...     production = AsyncProduction(queue_size=5)
        ...     await production.start(2, 3, producer, consumer)
        ...     await asyncio.sleep(2)
        ...     await production.shutdown()
        >>> asyncio.run(main())
    """

    def __init__(self, queue_size: int = 10):
        """初始化异步生产系统

        Args:
            queue_size: 异步任务队列的最大容量,默认为10
        """
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.producer_tasks: list[asyncio.Task] = []
        self.consumer_tasks: list[asyncio.Task] = []
        self.running = False
        self.error_callback: Callable[[Exception, Any], Coroutine] | None = None

    async def start(
        self,
        num_producers: int,
        num_consumers: int,
        producer_fn: Callable[[], Coroutine[Any, Any, Any]],
        consumer_fn: Callable[[Any], Coroutine[Any, Any, Any]],
    ) -> None:
        """启动异步生产消费系统

        Args:
            num_producers: 要创建的生产者协程数量
            num_consumers: 要创建的消费者协程数量
            producer_fn: 异步生产者函数,无参数,返回待处理的任务项
            consumer_fn: 异步消费者函数,接收任务项参数,返回处理结果

        Example:
            >>> await production.start(num_producers=2, num_consumers=3, producer_fn=async_producer, consumer_fn=async_consumer)
        """
        if self.running:
            mylog.debug('异步生产系统已经在运行中,忽略启动请求')
            return  # 防止重复启动

        self.running = True
        # 创建任务并保存引用
        self.producer_tasks = [asyncio.create_task(self._producer_loop(producer_fn)) for _ in range(num_producers)]
        self.consumer_tasks = [asyncio.create_task(self._consumer_loop(consumer_fn)) for _ in range(num_consumers)]
        mylog.debug(f'异步生产系统启动,{num_producers}个生产者,{num_consumers}个消费者')

    async def set_error_callback(self, callback: Callable[[Exception, Any], Coroutine]) -> None:
        """设置错误处理回调函数

        Args:
            callback: 异步回调函数,接收异常对象和失败的任务项作为参数

        Example:
            >>> async def error_handler(e, item):
            ...     mylog.debug(f'处理{item}时出错: {e}')
            >>> await production.set_error_callback(error_handler)
        """
        self.error_callback = callback

    async def _producer_loop(self, producer_fn: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        """生产者协程循环,持续生成任务项

        Args:
            producer_fn: 异步生产者函数,无参数,返回待处理的任务项
        """
        while self.running:
            try:
                item = await producer_fn()
                await self.queue.put(item)
            except asyncio.CancelledError:
                break  # 任务被取消时退出循环
            except Exception as e:
                mylog.debug(f'生产者异常: {e}')
                break  # 发生其他异常时退出循环

    async def _consumer_loop(self, consumer_fn: Callable[[Any], Coroutine[Any, Any, Any]]) -> None:
        """消费者协程循环,持续处理任务项

        Args:
            consumer_fn: 异步消费者函数,接收任务项参数,返回处理结果
        """
        while self.running:
            try:
                item = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=0.5,  # 关键优化：避免永久阻塞,定期检查running状态
                )
                try:
                    await consumer_fn(item)
                except Exception as e:
                    if self.error_callback:
                        await self.error_callback(e, item)
                    else:
                        mylog.debug(f'消费者异常: {e}')
                finally:
                    self.queue.task_done()  # 标记任务完成
            except TimeoutError:
                continue  # 超时后继续循环,检查running状态
            except asyncio.CancelledError:
                break  # 任务被取消时退出循环
            except Exception as e:
                mylog.debug(f'消费者循环异常: {e}')
                break  # 发生其他异常时退出循环

    async def shutdown(self) -> None:
        """安全停止异步生产消费系统

        停止所有生产者和消费者协程,清理资源,确保系统优雅退出。

        Example:
            >>> await production.shutdown()
        """
        if not self.running:
            mylog.debug('异步生产系统已经停止,忽略停止请求')
            return  # 防止重复停止

        self.running = False
        # 取消所有任务
        task_count = len(self.producer_tasks) + len(self.consumer_tasks)
        for task in self.producer_tasks + self.consumer_tasks:
            if not task.done():
                task.cancel()
        # 等待任务清理,允许异常被捕获和处理
        await asyncio.gather(*self.producer_tasks, *self.consumer_tasks, return_exceptions=True)
        # 清空任务引用列表
        self.producer_tasks.clear()
        self.consumer_tasks.clear()
        mylog.debug(f'异步生产系统已完全停止,共取消{task_count}个任务')

    async def wait_until_done(self, timeout: float | None = None) -> bool:
        """等待直到队列为空

        Args:
            timeout: 等待超时时间（秒）,None表示无限等待

        Returns:
            bool: 如果队列已清空返回True,超时返回False

        Example:
            >>> if await production.wait_until_done(timeout=5):
            ...     mylog.debug('所有任务已处理完成')
            ... else:
            ...     mylog.debug('等待超时')
        """
        try:
            await asyncio.wait_for(self.queue.join(), timeout=timeout)
            return True
        except TimeoutError:
            return False


class SyncProductionManager:
    """
    同步生产消费系统管理器

    提供更简洁的接口来管理同步版本的生产者-消费者模式，隐藏内部复杂性，
    适合快速上手和简化外部调用。

    Args:
        queue_size: 任务队列的最大容量,默认为10
        num_producers: 生产者数量,默认为1
        num_consumers: 消费者数量,默认为2

    Example:
        >>> def producer():
        ...     return random.randint(1, 100)
        >>> def consumer(item):
        ...     return item * 2
        >>> manager = SyncProductionManager(queue_size=5, num_producers=2, num_consumers=3)
        >>> manager.initialize(producer, consumer)
        >>> time.sleep(2)
        >>> results = manager.stop()
    """

    def __init__(self, queue_size: int = 10, num_producers: int = 1, num_consumers: int = 2):
        """初始化同步生产消费管理器

        Args:
            queue_size: 任务队列的最大容量,默认为10
            num_producers: 生产者数量,默认为1
            num_consumers: 消费者数量,默认为2
        """
        self.queue_size = queue_size
        self.num_producers = num_producers
        self.num_consumers = num_consumers
        self.system: Production | None = None

    def initialize(self, producer_fn: Callable[[], Any], consumer_fn: Callable[[Any], Any], error_callback: Callable[[Exception, Any], None] | None = None) -> None:
        """初始化并启动生产消费系统

        Args:
            producer_fn: 生产者函数,无参数,返回待处理的任务项
            consumer_fn: 消费者函数,接收任务项参数,返回处理结果
            error_callback: 错误处理回调函数,可选
        """
        if self.system is not None:
            mylog.debug('系统已经初始化,请先停止当前系统')
            return

        # 创建生产系统
        self.system = Production(queue_size=self.queue_size)

        # 设置错误回调
        if error_callback:
            self.system.set_error_callback(error_callback)

        # 添加生产者
        for _ in range(self.num_producers):
            self.system.add_producer(producer_fn)

        # 添加消费者
        for _ in range(self.num_consumers):
            self.system.add_consumer(consumer_fn)

        mylog.debug(f'同步生产消费系统已初始化: {self.num_producers}个生产者, {self.num_consumers}个消费者')

    def stop(self, timeout: float | None = 1) -> list[Any]:
        """停止生产消费系统并获取结果

        Args:
            timeout: 等待超时时间（秒），None表示无限等待

        Returns:
            list[Any]: 所有处理结果的列表
        """
        if self.system is None:
            mylog.debug('系统尚未初始化')
            return []

        results = self.system.shutdown(timeout=timeout)
        stats = self.system.get_stats()
        mylog.debug(f'同步生产消费系统已停止,共处理{len(results)}个任务')
        mylog.debug(f'系统运行统计: {stats}')

        # 重置系统引用
        self.system = None
        return results

    def get_stats(self) -> dict:
        """获取当前系统运行统计信息

        Returns:
            dict: 包含系统运行指标的字典
        """
        if self.system is None:
            return {'error': '系统尚未初始化'}
        return self.system.get_stats()

    def get_result_list(self) -> list[Any]:
        """获取当前所有的处理结果列表

        Returns:
            list[Any]: 所有已处理完成的结果列表
        """
        if self.system is None:
            return []
        return self.system.get_result_list()

    def get_task_count(self) -> int:
        """获取当前待处理的任务数量

        Returns:
            int: 待处理的任务数量
        """
        if self.system is None:
            return 0
        return self.system.get_task_count()

    @property
    def is_running(self) -> bool:
        """检查系统是否正在运行

        Returns:
            bool: 系统是否正在运行
        """
        return self.system is not None


class AsyncProductionManager:
    """
    异步生产消费系统管理器

    提供更简洁的接口来管理异步版本的生产者-消费者模式，隐藏内部复杂性，
    适合快速上手和简化外部调用。

    Args:
        queue_size: 任务队列的最大容量,默认为10
        num_producers: 生产者协程数量,默认为1
        num_consumers: 消费者协程数量,默认为2

    Example:
        >>> async def producer():
        ...     await asyncio.sleep(0.1)
        ...     return random.randint(1, 100)
        >>> async def consumer(item):
        ...     await asyncio.sleep(0.2)
        ...     return item * 2
        >>> async def main():
        ...     manager = AsyncProductionManager(queue_size=5, num_producers=2, num_consumers=3)
        ...     await manager.initialize(producer, consumer)
        ...     await asyncio.sleep(2)
        ...     await manager.stop()
        >>> asyncio.run(main())
    """

    def __init__(self, queue_size: int = 10, num_producers: int = 1, num_consumers: int = 2):
        """初始化异步生产消费管理器

        Args:
            queue_size: 任务队列的最大容量,默认为10
            num_producers: 生产者协程数量,默认为1
            num_consumers: 消费者协程数量,默认为2
        """
        self.queue_size = queue_size
        self.num_producers = num_producers
        self.num_consumers = num_consumers
        self.system: AsyncProduction | None = None

    async def initialize(
        self, producer_fn: Callable[[], Coroutine[Any, Any, Any]], consumer_fn: Callable[[Any], Coroutine[Any, Any, Any]], error_callback: Callable[[Exception, Any], Coroutine] | None = None
    ) -> None:
        """初始化并启动异步生产消费系统

        Args:
            producer_fn: 异步生产者函数,无参数,返回待处理的任务项
            consumer_fn: 异步消费者函数,接收任务项参数,返回处理结果
            error_callback: 异步错误处理回调函数,可选
        """
        if self.system is not None:
            mylog.debug('异步系统已经初始化,请先停止当前系统')
            return

        # 创建异步生产系统
        self.system = AsyncProduction(queue_size=self.queue_size)

        # 设置错误回调
        if error_callback:
            await self.system.set_error_callback(error_callback)

        # 启动系统
        await self.system.start(num_producers=self.num_producers, num_consumers=self.num_consumers, producer_fn=producer_fn, consumer_fn=consumer_fn)

    async def stop(self, wait_for_completion: bool = True, timeout: float | None = 3) -> None:
        """停止异步生产消费系统

        Args:
            wait_for_completion: 是否等待所有任务处理完成
            timeout: 等待超时时间（秒）,None表示无限等待
        """
        if self.system is None:
            mylog.debug('异步系统尚未初始化')
            return

        # 可选：等待队列处理完成
        if wait_for_completion:
            mylog.debug('等待所有任务处理完成...')
            done = await self.system.wait_until_done(timeout=timeout)
            mylog.debug(f'队列处理{"完成" if done else "超时"}')

        # 停止系统
        await self.system.shutdown()

        # 重置系统引用
        self.system = None

    async def wait_until_done(self, timeout: float | None = None) -> bool:
        """等待直到队列为空

        Args:
            timeout: 等待超时时间（秒）,None表示无限等待

        Returns:
            bool: 如果队列已清空返回True,超时返回False
        """
        if self.system is None:
            return True  # 系统未初始化,视为已完成
        return await self.system.wait_until_done(timeout=timeout)

    @property
    def is_running(self) -> bool:
        """检查系统是否正在运行

        Returns:
            bool: 系统是否正在运行
        """
        return self.system is not None and self.system.running
