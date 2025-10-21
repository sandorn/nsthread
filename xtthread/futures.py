# !/usr/bin/env python3
"""
==============================================================
线程池增强模块 - 提供多种线程池实现及异步任务处理功能
------------------------------------------------------
本模块提供四种不同类型的线程池实现，满足从简单到复杂的并发任务需求。
主要适用于需要高效并发执行同步和异步函数的场景，支持任务结果收集、
异常处理和自动资源管理等功能。

核心实现：
- BaseThreadRunner: 极简线程池实现，使用信号量控制并发线程数量
- EnhancedThreadPool: 增强型线程池，扩展标准ThreadPoolExecutor，提供结果收集和异常处理
- AsyncThreadPool: 异步增强型线程池，支持同步和异步函数的混合执行
- FutureThreadPool: 基于asyncio.run的线程池，专注于一次性任务执行场景

主要特点：
- 统一的任务提交和结果获取接口
- 自动处理同步和异步函数的执行差异
- 完善的异常捕获和处理机制
- 支持上下文管理器语法，确保资源正确释放
- 线程安全的实现，适用于多线程环境
==============================================================
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
import os
from collections.abc import Callable, Sequence
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import Lock, Semaphore
from typing import Any, Self

from xtlog import mylog

from .thread import ThreadBase

# 定义任务参数类型别名，支持两种格式：
# - 简单格式：单个参数值 (Any)
# - 复杂格式：包含位置参数元组和关键字参数字典的元组 ((args_tuple), {kwargs_dict})
TaskParams = Any | tuple[tuple[Any, ...], dict[str, Any]]


@dataclass
class TaskResult:
    """任务结果包装类

    Attributes:
        success: 任务是否执行成功
        result: 任务执行成功时的返回结果
        error: 任务执行失败时的异常对象
    """

    success: bool
    result: Any = None
    error: Exception | None = None


def handle_exception(exc: Exception, handler: Callable[[Exception], Any] | None = None, custom_message: str = '', re_raise: bool = False) -> None:
    """统一异常处理函数

    Args:
        exc: 捕获的异常
        handler: 自定义异常处理器
        custom_message: 自定义错误消息
        re_raise: 是否重新抛出异常
    """
    # 记录异常信息
    message = f'{custom_message}: {exc!s}' if custom_message else str(exc)
    mylog.error(message, exc_info=True)

    # 如果有自定义处理器，调用它
    if handler:
        handler(exc)

    # 如果需要重新抛出异常
    if re_raise:
        raise


class BaseThreadRunner:
    """极简线程池实现

    提供最基础的线程池功能，使用信号量控制并发线程数量。
    适用于简单场景下的任务并发执行，不提供高级功能如结果收集和异常处理。
    """

    def __init__(self, max_workers: int = 10):
        """初始化线程池

        Args:
            max_workers: 最大工作线程数，默认为10
        """
        self.max_workers = max_workers
        self._semaphore = Semaphore(max_workers)
        self._threads: list[ThreadBase] = []

    def submit(self, target: Callable, *args: Any, **kwargs: Any) -> ThreadBase:
        """提交任务到线程池

        创建新线程执行指定函数，并使用信号量控制并发线程数量。
        当没有可用线程资源时，此方法会阻塞直到有线程释放。

        Args:
            target: 要执行的目标函数
            *args: 传递给目标函数的位置参数
            **kwargs: 传递给目标函数的关键字参数

        Returns:
            ThreadBase: 创建的线程对象
        """
        # 等待信号量，确保不超过最大线程数
        self._semaphore.acquire()

        # 创建线程
        thread = ThreadBase(target=target, args=args, kwargs=kwargs)

        # 重写完成逻辑，确保线程结束后释放信号量
        original_run = thread.run

        def wrapped_run():
            try:
                original_run()
            finally:
                self._semaphore.release()

        thread.run = wrapped_run
        thread.start()
        self._threads.append(thread)

        return thread

    @property
    def active_threads(self) -> int:
        """获取当前活跃线程数

        直接统计活跃线程数，不依赖于Semaphore的内部属性。

        Returns:
            int: 当前正在运行的线程数量
        """
        return sum(1 for thread in self._threads if thread.is_alive())

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池

        Args:
            wait: 是否等待所有线程完成执行
        """
        if not wait:
            return

        for thread in self._threads:
            thread.stop()

    def get_results(self) -> list[Any]:
        """等待所有任务完成并返回结果列表

        Returns:
            list[Any]: 按提交顺序排列的任务执行结果列表
        """
        results = []
        for thread in self._threads:
            result = thread.get_result()
            results.append(result)

        return results


class EnhancedThreadPool:
    """增强型线程池，提供任务结果收集和异常处理功能

    扩展了标准ThreadPoolExecutor，支持任务结果自动收集、统一异常处理、批量任务提交等功能。
    适用于需要集中管理和监控多任务执行的场景。
    """

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = 'EnhancedThreadPool',
        exception_handler: Callable[[Exception], Any] | None = None,
    ):
        """初始化增强型线程池

        Args:
            max_workers: 最大工作线程数，默认为CPU核心数*4
            thread_name_prefix: 线程名前缀，默认为"EnhancedThreadPool"
            exception_handler: 异常处理器，默认为None
        """
        base_workers = os.cpu_count() or 4  # 默认IO密集型配置
        self.max_workers = max_workers if max_workers is not None else base_workers * 4
        self.thread_name_prefix = thread_name_prefix
        self.exception_handler = exception_handler
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix=self.thread_name_prefix)
        self._future_tasks: list[Future] = []
        self.results: list[TaskResult] = []

    def __enter__(self):
        """支持上下文管理器协议的入口方法"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议的退出方法，自动关闭线程池"""
        self.shutdown(wait=True)

    def _task_wrapper(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """任务包装器，用于处理异常

        Args:
            fn: 要执行的目标函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Any: 任务执行结果或异常处理结果
        """
        try:
            return fn(*args, **kwargs)
        except Exception as err:
            if self.exception_handler:
                self.exception_handler(err)
            raise

    def submit_task(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        """提交单个任务到线程池执行

        Args:
            fn: 要执行的目标函数
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            Future: Future对象用于跟踪任务状态和获取结果

        Raises:
            RuntimeError: 当线程池已关闭时尝试提交任务
        """
        future = self.executor.submit(self._task_wrapper, fn, *args, **kwargs)
        self._future_tasks.append(future)
        return future

    def submit_tasks(
        self,
        fn: Callable[..., Any],
        iterables: Sequence[TaskParams],
    ) -> list[Future]:
        """批量提交任务到线程池，支持智能参数格式检测

        Args:
            fn: 要执行的目标函数
            iterables: 任务参数的可迭代对象
                - 简单格式: [item1, item2, ...]
                - 复杂格式: [((args_tuple), {kwargs_dict}), ...]

        Returns:
            list[Future]: 提交的任务Future对象列表
        """
        futures = []
        if not iterables:
            return futures

        # 统一处理所有参数项
        for item in iterables:
            if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[1], dict):
                # 复杂格式: (args_tuple, kwargs_dict)
                arg_tuple, kwargs_dict = item
                future = self.submit_task(fn, *arg_tuple, **kwargs_dict)
            else:
                # 简单格式: 单个参数
                future = self.submit_task(fn, item)
            futures.append(future)

        return futures

    def wait_all_completed(self, timeout: float | None = None) -> list[Any]:
        """等待所有任务完成并获取结果

        Args:
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            list[Any]: 按提交顺序排列的任务结果列表
        """
        # 保存当前所有future任务
        all_futures = self._future_tasks.copy()

        # 如果没有待处理任务，直接返回空列表
        if not all_futures:
            return []

        # 等待任务完成，根据timeout决定等待策略
        if timeout is None:
            # 无超时限制，等待所有任务完成
            done, not_done = wait(all_futures, timeout=None, return_when=ALL_COMPLETED)
        else:
            # 有超时限制，等待一段时间后返回已完成的任务
            done, not_done = wait(all_futures, timeout=timeout, return_when=FIRST_COMPLETED)

        # 更新未完成的任务列表
        self._future_tasks = list(not_done)

        # 按提交顺序收集结果
        results = []
        for future in all_futures:
            if future in done:
                try:
                    # 获取任务结果
                    result = future.result()
                    results.append(TaskResult(success=True, result=result))
                except Exception as err:
                    # 处理异常结果
                    results.append(TaskResult(success=False, error=err))
        self.results = results
        return results

    def get_results(self, timeout: float | None = None) -> list[Any]:
        """获取所有任务的执行结果

        Returns:
            list[Any]: 包含所有任务执行结果的列表
        """
        return [res.result if res.success else res.error for res in self.results]

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池并清理资源

        Args:
            wait: 是否等待所有任务完成后再关闭
        """
        try:
            self.executor.shutdown(wait=wait)
        except Exception as exc:
            handle_exception(exc=exc, custom_message='EnhancedThreadPool.shutdown', re_raise=True)


class AsyncThreadPool:
    """异步增强型线程池，支持同步和异步函数执行的统一接口

    该类提供了一个功能强大的线程池实现，能够处理同步函数和异步函数的执行，
    支持任务提交、批量任务处理、回调函数、异步等待以及自动资源管理。
    适用于需要在多线程环境中混合执行同步和异步代码的场景。
    """

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = 'AsyncThreadPool',
        exception_handler: Callable[[Exception], Any] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        """初始化异步增强型线程池

        Args:
            max_workers: 最大工作线程数，默认为CPU核心数*4
            thread_name_prefix: 线程名前缀，默认为"AsyncThreadPool"
            exception_handler: 异常处理器，默认为None
            loop: 可选的事件循环对象
        """
        base_workers = os.cpu_count() or 4  # 默认IO密集型配置
        self.max_workers = max_workers if max_workers is not None else base_workers * 4
        self.thread_name_prefix = thread_name_prefix
        self.exception_handler = exception_handler

        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix=self.thread_name_prefix)
        self._future_tasks: list[asyncio.Future] = []
        self.results: list[TaskResult] = []
        self._loop = loop
        self._loop_lock = Lock()  # 添加线程锁保护事件循环创建
        self._shutting_down = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """获取或创建事件循环对象

        线程安全地获取事件循环，如果不存在则创建新的。

        Returns:
            asyncio.AbstractEventLoop: 事件循环对象
        """
        if self._loop is None:
            # 使用锁确保线程安全
            with self._loop_lock:
                # 双重检查，避免重复创建
                if self._loop is None:
                    try:
                        self._loop = asyncio.get_running_loop()
                    except RuntimeError:
                        # 创建新的事件循环但不设置为当前线程的循环
                        self._loop = asyncio.new_event_loop()
        return self._loop

    def __enter__(self):
        """支持上下文管理器协议的入口方法"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议的退出方法，自动关闭线程池"""
        self.shutdown(wait=True)

    def _sync_wrapper(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """执行同步函数并处理异常

        Args:
            fn: 要执行的同步函数
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            Any: 函数执行的结果，如果发生异常则返回None
        """
        try:
            return fn(*args, **kwargs)
        except Exception as err:
            if self.exception_handler:
                self.exception_handler(err)
            raise

    async def _async_wrapper(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """异步执行异步函数并处理异常

        Args:
            fn: 要执行的异步函数
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            Any: 函数执行的结果，如果发生异常则返回None
        """
        try:
            return await fn(*args, **kwargs)
        except Exception as err:
            if self.exception_handler:
                self.exception_handler(err)
            raise

    def _task_wrapper(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """统一的任务包装器，根据函数类型选择执行方式

        对于异步函数，创建新的事件循环并执行；对于同步函数，直接执行。
        自动处理执行过程中的异常。

        Args:
            fn: 要执行的函数（同步或异步）
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            Any: 函数执行的结果，如果发生异常则返回None
        """
        if asyncio.iscoroutinefunction(fn):
            # 对于异步函数，创建新的事件循环
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self._async_wrapper(fn, *args, **kwargs))
            except Exception as err:
                handle_exception(exc=err, handler=self.exception_handler, custom_message=f'AsyncThreadPool._task_wrapper: {fn.__name__}')
            finally:
                # 简单关闭循环
                try:
                    loop.close()
                except Exception as err:
                    handle_exception(exc=err, handler=self.exception_handler, custom_message=f'AsyncThreadPool._task_wrapper: {fn.__name__}')
        else:
            # 对于同步函数，直接执行
            return self._sync_wrapper(fn, *args, **kwargs)

    def submit_task(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> asyncio.Future:
        """提交单个任务到线程池执行

        Args:
            fn: 要执行的函数（同步或异步）
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            asyncio.Future: 表示任务执行的 Future 对象

        Raises:
            RuntimeError: 当线程池正在关闭时
        """
        if self._shutting_down:
            raise RuntimeError('Cannot submit task to a pool that is shutting down')

        task_func = functools.partial(self._task_wrapper, fn, *args, **kwargs)
        future = self.loop.run_in_executor(self.executor, task_func)
        self._future_tasks.append(future)
        return future

    def submit_tasks(
        self,
        fn: Callable[..., Any],
        iterables: Sequence[TaskParams],
    ) -> list[asyncio.Future]:
        """批量提交任务到线程池

        Args:
            fn: 要执行的目标函数
            iterables: 任务参数的可迭代对象
                - 简单格式: [item1, item2, ...]
                - 复杂格式: [((args_tuple), {kwargs_dict}), ...]

        Returns:
            list[Future]: 提交的任务Future对象列表

        Raises:
            RuntimeError: 当线程池正在关闭时
        """
        if self._shutting_down:
            raise RuntimeError('Cannot submit tasks to a pool that is shutting down')

        futures = []
        if not iterables:
            return futures

        # 统一处理所有参数项
        for item in iterables:
            if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[1], dict):
                # 复杂格式: (args_tuple, kwargs_dict)
                arg_tuple, kwargs_dict = item
                future = self.submit_task(fn, *arg_tuple, **kwargs_dict)
            else:
                # 简单格式: 单个参数
                future = self.submit_task(fn, item)
            futures.append(future)

        return futures

    def wait_all_completed(self, timeout: float | None = None) -> list[Any]:
        """等待所有提交的任务完成并获取结果

        Args:
            timeout: 等待超时时间（秒），None表示无限等待

        Returns:
            list[Any]: 所有任务结果列表,按提交顺序排列
        """
        if not self._future_tasks:
            return []

        try:
            # 使用 asyncio.wait 来等待所有任务完成
            if self.loop.is_running():
                # 如果循环正在运行，使用线程安全的方式等待
                future = asyncio.run_coroutine_threadsafe(self._wait_all_completed_async(timeout), self.loop)
                return future.result(timeout=timeout)
            # 如果循环未运行，直接等待
            return self.loop.run_until_complete(self._wait_all_completed_async(timeout))
        except Exception:
            return []

    async def _wait_all_completed_async(self, timeout: float | None = None) -> list[Any]:
        """异步等待所有任务完成的内部方法

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            list[Any]: 所有已完成任务的结果列表，按提交顺序排列
        """
        if not self._future_tasks:
            return []

        try:
            # 保存当前所有 future 的副本，用于按提交顺序收集结果
            all_futures = self._future_tasks.copy()

            if timeout is not None:
                # 使用 asyncio.wait 带超时
                _, pending = await asyncio.wait(all_futures, timeout=timeout, return_when=asyncio.ALL_COMPLETED)
                # 只保留未完成的任务
                self._future_tasks = list(pending)
            else:
                # 无超时，等待所有任务完成
                await asyncio.gather(*all_futures, return_exceptions=True)
                _ = set(all_futures)
                self._future_tasks.clear()

            # 按提交顺序收集结果
            results = []
            for future in all_futures:
                if future.done():
                    try:
                        result = future.result()
                        # 直接创建成功的 TaskResult
                        results.append(TaskResult(success=True, result=result))
                    except Exception as err:
                        # 处理异常情况
                        results.append(TaskResult(success=False, error=err))

            self.results = results
            return results
        except TimeoutError:
            return []

    def get_results(self, timeout: float | None = None) -> list[Any]:
        """获取所有任务的执行结果

        Returns:
            list[Any]: 包含所有任务执行结果的列表
        """
        return [res.result if res.success else res.error for res in self.results]

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池并清理资源

        Args:
            wait: 是否等待所有任务完成后再关闭

        Raises:
            Exception: 当关闭线程池过程中出现严重错误时
        """
        if self._shutting_down:
            return

        self._shutting_down = True

        # 等待剩余任务完成
        if wait and self._future_tasks:
            try:
                # 使用 wait_all_completed 来等待
                self.wait_all_completed(timeout=5)
            except Exception as exc:
                handle_exception(exc=exc, custom_message='AsyncThreadPool.shutdown.wait')

        # 关闭线程池
        try:
            self.executor.shutdown(wait=wait)
        except Exception as exc:
            handle_exception(exc=exc, custom_message='AsyncThreadPool.shutdown', re_raise=True)
            # 额外清理：确保主循环被正确关闭（如果是我们创建的）

        if hasattr(self, '_loop') and self._loop and not self._loop.is_closed():
            with contextlib.suppress(Exception):
                # 如果循环不在运行，就关闭它
                if not self._loop.is_running():
                    self._loop.close()


class FutureThreadPool:
    """异步增强型线程池，使用 asyncio.run 作为最外层入口

    专注于一次性任务执行场景，提供简洁高效的API接口。
    自动管理异步和同步函数的执行，支持批量任务处理和结果收集。
    """

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = 'FutureThreadPool',
        exception_handler: Callable[[Exception], Any] | None = None,
    ):
        """初始化FutureThreadPool线程池

        Args:
            max_workers: 最大工作线程数，默认为CPU核心数*4
            thread_name_prefix: 线程名前缀，默认为"FutureThreadPool"
            exception_handler: 异常处理器，默认为None
        """
        base_workers = os.cpu_count() or 4  # 默认IO密集型配置
        self.max_workers = max_workers if max_workers is not None else base_workers * 4
        self.thread_name_prefix = thread_name_prefix
        self.exception_handler = exception_handler

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    async def _submit_task(self, fn: Callable[..., Any], *args, **kwargs) -> TaskResult:
        """提交单个任务，自动检测函数类型并处理异常

        根据函数类型自动选择异步或同步执行路径，并统一处理异常

        Args:
            fn: 要执行的函数（同步或异步）
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            TaskResult: 任务执行结果包装对象
        """
        if inspect.iscoroutinefunction(fn):
            # 异步函数处理路径
            try:
                result = await asyncio.create_task(fn(*args, **kwargs))
                return TaskResult(success=True, result=result)
            except Exception as err:
                return TaskResult(success=False, error=err)
        else:
            # 同步函数处理路径
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix=self.thread_name_prefix) as executor:
                # 定义内部函数用于异常处理
                def sync_execute():
                    try:
                        result = fn(*args, **kwargs)
                        return TaskResult(success=True, result=result)
                    except Exception as err:
                        return TaskResult(success=False, error=err)

                # 在线程池中执行同步函数
                result = await loop.run_in_executor(executor, sync_execute)
                # 如果结果是TaskResult，直接返回；否则包装成成功的TaskResult
                if isinstance(result, TaskResult):
                    return result
                return TaskResult(success=True, result=result)

    async def _submit_tasks(self, fn: Callable[..., Any], iterables: Sequence[TaskParams]) -> list[TaskResult]:
        """批量提交任务

        Args:
            fn: 要执行的目标函数
            iterables: 任务参数的可迭代对象

        Returns:
            list[TaskResult]: 所有任务的执行结果包装对象列表
        """
        tasks = []
        if not iterables:
            return tasks

        # 统一处理所有参数项
        for item in iterables:
            if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[1], dict):
                # 复杂格式: (args_tuple, kwargs_dict)
                arg_tuple, kwargs_dict = item
                task = self._submit_task(fn, *arg_tuple, **kwargs_dict)
            else:
                # 简单格式: 单个参数
                task = self._submit_task(fn, item)
            tasks.append(task)

        # 等待所有任务完成并收集结果
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常情况，确保所有结果都是TaskResult类型
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(TaskResult(success=False, error=result))
            elif isinstance(result, TaskResult):
                processed_results.append(result)
            else:
                processed_results.append(TaskResult(success=True, result=result))

        return processed_results

    def submit_task(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> TaskResult:
        """同步提交单个任务

        使用asyncio.run作为最外层入口，自动管理事件循环生命周期

        Args:
            fn: 要执行的函数（同步或异步）
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            TaskResult: 任务执行结果包装对象
        """
        return asyncio.run(self._submit_task(fn, *args, **kwargs))

    def submit_tasks(
        self,
        fn: Callable[..., Any],
        iterables: Sequence[TaskParams],
    ) -> list[TaskResult]:
        """批量提交任务到线程池

        使用asyncio.run作为最外层入口，自动管理事件循环生命周期

        Args:
            fn: 要执行的目标函数
            iterables: 任务参数的可迭代对象

        Returns:
            list[TaskResult]: 所有任务的执行结果包装对象列表
        """
        return asyncio.run(self._submit_tasks(fn, iterables))


__all__ = [
    'AsyncThreadPool',
    'BaseThreadRunner',
    'EnhancedThreadPool',
    'FutureThreadPool',
]
