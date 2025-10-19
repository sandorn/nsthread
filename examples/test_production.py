"""
==============================================================
Description  : production.py模块测试代码
Develop      : VSCode
Author       : sandorn sandorn@live.cn
Date         : 2024-10-09 10:05:00
==============================================================
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
import unittest

from xtthread.production import AsyncProduction, AsyncProductionManager, Production, SyncProductionManager


class TestProduction(unittest.TestCase):
    """测试Production类（同步生产者-消费者模式）的功能"""

    def setUp(self):
        """测试前的准备工作"""
        self.production = None

    def tearDown(self):
        """测试后的清理工作"""
        if self.production:
            self.production.shutdown()

    def test_init(self):
        """测试初始化功能"""
        production = Production(queue_size=3)
        assert production.queue.maxsize == 3
        assert production.tasks == 0
        assert production.error_callback is None
        assert not production.running.is_set()
        production.shutdown()

    def test_add_producer_and_consumer(self):
        """测试添加生产者和消费者功能"""
        self.production = Production(queue_size=5)

        def simple_producer():
            return 42

        def simple_consumer(item):
            return item * 2

        # 测试添加生产者
        initial_producer_count = len(self.production.producers)
        self.production.add_producer(simple_producer, 'TestProducer')
        assert len(self.production.producers) == initial_producer_count + 1

        # 测试添加消费者
        initial_consumer_count = len(self.production.consumers)
        self.production.add_consumer(simple_consumer, 'TestConsumer')
        assert len(self.production.consumers) == initial_consumer_count + 1

        # 验证线程已启动
        producer_thread = self.production.producers[-1]
        consumer_thread = self.production.consumers[-1]
        assert producer_thread.is_alive()
        assert consumer_thread.is_alive()
        assert producer_thread.name == 'TestProducer'
        assert consumer_thread.name == 'TestConsumer'

    def test_basic_producer_consumer_flow(self):
        """测试基本的生产者-消费者流程"""
        self.production = Production(queue_size=10)
        results_produced = []
        results_consumed = []

        def producer():
            item = len(results_produced) + 1
            results_produced.append(item)
            if len(results_produced) >= 5:  # 限制生产数量
                time.sleep(1)  # 停止生产更多
            return item

        def consumer(item):
            results_consumed.append(item)
            return item * 2

        self.production.add_producer(producer)
        self.production.add_consumer(consumer)

        # 运行一段时间
        time.sleep(0.5)

        # 停止并获取结果
        final_results = self.production.shutdown()

        # 验证生产和消费都有发生
        assert len(results_produced) > 0
        assert len(results_consumed) > 0
        assert len(final_results) > 0

    def test_error_handling_with_callback(self):
        """测试带错误回调的异常处理"""
        self.production = Production(queue_size=5)
        captured_errors = []
        captured_items = []

        def error_callback(exception, item):
            captured_errors.append(exception)
            captured_items.append(item)

        def producer():
            return 42

        def failing_consumer(item):
            raise ValueError(f'消费失败: {item}')

        self.production.set_error_callback(error_callback)
        self.production.add_producer(producer)
        self.production.add_consumer(failing_consumer)

        time.sleep(0.3)  # 让一些错误发生
        self.production.shutdown()

        # 验证错误回调被调用
        assert len(captured_errors) > 0
        assert len(captured_items) > 0

        # 验证错误类型正确
        for error in captured_errors:
            assert isinstance(error, ValueError)
            assert '消费失败' in str(error)

    def test_error_handling_without_callback(self):
        """测试没有错误回调时的异常处理"""
        self.production = Production(queue_size=5)

        def producer():
            return 42

        def failing_consumer(item):
            raise ValueError(f'消费失败: {item}')

        # 记录测试开始前的任务计数
        initial_tasks = self.production.tasks

        # 添加生产者和消费者
        self.production.add_producer(producer)
        self.production.add_consumer(failing_consumer)

        time.sleep(0.3)

        # 即使发生异常，系统也应该能够正常关闭
        results = self.production.shutdown()

        # 验证系统能够继续运行，没有因为异常而崩溃
        assert results is not None
        # 验证任务已经被处理（虽然可能失败）
        assert self.production.tasks > initial_tasks

    def test_get_methods(self):
        """测试获取结果和状态的方法"""
        self.production = Production(queue_size=5)

        def producer():
            time.sleep(0.1)
            return 10

        def consumer(item):
            time.sleep(0.1)
            return item * 5

        self.production.add_producer(producer)
        self.production.add_consumer(consumer)

        # 等待一些结果产生
        time.sleep(0.3)

        # 测试获取任务计数
        task_count = self.production.get_task_count()
        assert task_count >= 0

        # 测试获取结果列表
        results = self.production.get_result_list()
        assert isinstance(results, list)

        # 如果有结果，测试获取单个结果
        if results:
            assert results[0] == 50  # 10 * 5

    def test_queue_size_limit(self):
        """测试队列大小限制"""
        production = Production(queue_size=2)

        def fast_producer():
            return random.randint(1, 100)

        def slow_consumer(item):
            time.sleep(0.2)  # 消费很慢
            return item

        production.add_producer(fast_producer)
        production.add_consumer(slow_consumer)

        time.sleep(0.5)  # 让生产者尝试填满队列

        # 队列大小不应超过限制
        assert production.queue.qsize() <= 2

        production.shutdown()

    def test_multiple_producers_consumers(self):
        """测试多个生产者和消费者"""
        self.production = Production(queue_size=20)
        counter = {'value': 0}
        lock = threading.Lock()

        def producer():
            with lock:
                counter['value'] += 1
                return counter['value']

        def consumer(item):
            return item * 3

        # 添加多个生产者和消费者
        for i in range(2):
            self.production.add_producer(producer, f'Producer-{i}')

        for i in range(2):
            self.production.add_consumer(consumer, f'Consumer-{i}')

        # 运行一段时间
        time.sleep(0.5)

        # 停止并获取结果
        results = self.production.shutdown()

        # 验证多个线程工作
        assert len(self.production.producers) == 2
        assert len(self.production.consumers) == 2
        assert len(results) > 0


class TestAsyncProduction(unittest.TestCase):
    """测试AsyncProduction类（异步生产者-消费者模式）的功能"""

    def setUp(self):
        """测试前的准备工作"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """测试后的清理工作"""
        try:
            # 清理所有未完成的任务
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            self.loop.close()

    def test_init(self):
        """测试初始化功能"""

        async def test():
            production = AsyncProduction(queue_size=3)
            assert production.queue.maxsize == 3
            assert not production.running
            assert len(production.producer_tasks) == 0
            assert len(production.consumer_tasks) == 0
            assert production.error_callback is None

        self.loop.run_until_complete(test())

    def test_start_and_shutdown(self):
        """测试启动和关闭系统功能"""

        async def test():
            production = AsyncProduction()

            async def producer():
                await asyncio.sleep(0.01)
                return 42

            async def consumer(item):
                await asyncio.sleep(0.01)
                return item * 2

            # 测试启动
            await production.start(1, 1, producer, consumer)

            # 验证系统已启动
            assert production.running
            assert len(production.producer_tasks) == 1
            assert len(production.consumer_tasks) == 1

            # 验证任务都在运行
            for task in production.producer_tasks + production.consumer_tasks:
                assert not task.done()

            # 测试关闭
            await production.shutdown()

            # 验证系统已停止
            assert not production.running
            assert len(production.producer_tasks) == 0
            assert len(production.consumer_tasks) == 0

        self.loop.run_until_complete(test())

    def test_basic_flow(self):
        """测试基本的异步生产者-消费者流程"""

        async def test():
            production = AsyncProduction(queue_size=10)
            produced_count = 0
            consumed_count = 0

            async def producer():
                nonlocal produced_count
                if produced_count >= 3:  # 限制生产数量
                    await asyncio.sleep(1)  # 长时间休眠停止生产
                    return None

                await asyncio.sleep(0.01)
                produced_count += 1
                return produced_count

            async def consumer(item):
                nonlocal consumed_count
                await asyncio.sleep(0.02)
                consumed_count += 1
                return item * 2

            await production.start(1, 1, producer, consumer)

            # 运行一段时间让生产者产生一些项目
            await asyncio.sleep(0.2)

            await production.shutdown()

            # 验证生产和消费都有发生
            assert produced_count > 0
            assert consumed_count > 0

        self.loop.run_until_complete(test())

    def test_error_handling_with_callback(self):
        """测试带错误回调的异常处理"""

        async def test():
            production = AsyncProduction()
            captured_errors = []
            captured_items = []

            async def error_callback(exception, item):
                captured_errors.append(exception)
                captured_items.append(item)

            async def producer():
                await asyncio.sleep(0.01)
                return 42

            async def failing_consumer(item):
                raise ValueError(f'消费失败: {item}')

            await production.set_error_callback(error_callback)
            await production.start(1, 1, producer, failing_consumer)

            await asyncio.sleep(0.1)
            await production.shutdown()

            # 验证错误回调被调用
            assert len(captured_errors) > 0
            assert len(captured_items) > 0

            # 验证错误类型正确
            for error in captured_errors:
                assert isinstance(error, ValueError)
                assert '消费失败' in str(error)

        self.loop.run_until_complete(test())

    def test_error_handling_without_callback(self):
        """测试没有错误回调时的异常处理"""

        async def test():
            production = AsyncProduction()

            async def producer():
                await asyncio.sleep(0.01)
                return 42

            async def failing_consumer(item):
                raise ValueError(f'消费失败: {item}')

            # 添加生产者和消费者
            await production.start(1, 1, producer, failing_consumer)
            await asyncio.sleep(0.1)

            # 即使发生异常，系统也应该能够正常关闭
            await production.shutdown()

            # 验证系统已停止
            assert not production.running
            assert len(production.producer_tasks) == 0
            assert len(production.consumer_tasks) == 0

        self.loop.run_until_complete(test())

    def test_duplicate_start_protection(self):
        """测试重复启动保护"""

        async def test():
            production = AsyncProduction()

            async def producer():
                return 1

            async def consumer(item):
                return item

            # 第一次启动
            await production.start(1, 1, producer, consumer)
            initial_tasks = len(production.producer_tasks) + len(production.consumer_tasks)

            # 第二次启动（应该被忽略）
            await production.start(2, 2, producer, consumer)
            final_tasks = len(production.producer_tasks) + len(production.consumer_tasks)

            # 任务数量不应该改变
            assert initial_tasks == final_tasks

            await production.shutdown()

        self.loop.run_until_complete(test())

    def test_duplicate_shutdown_protection(self):
        """测试重复关闭保护"""

        async def test():
            production = AsyncProduction()

            async def producer():
                return 1

            async def consumer(item):
                return item

            await production.start(1, 1, producer, consumer)

            # 第一次关闭
            await production.shutdown()

            # 验证系统已停止
            first_running_state = production.running

            # 第二次关闭（应该被忽略）
            await production.shutdown()

            # 验证运行状态没有变化
            second_running_state = production.running

            # 第二次关闭不应该改变运行状态
            assert not first_running_state
            assert not second_running_state
            assert not production.running

        self.loop.run_until_complete(test())

    def test_wait_until_done_success(self):
        """测试等待完成成功功能"""

        async def test():
            production = AsyncProduction()
            task_count = 0

            async def producer():
                nonlocal task_count
                if task_count >= 2:  # 只生产2个项目
                    await asyncio.sleep(10)  # 长时间休眠
                    return None

                await asyncio.sleep(0.01)
                task_count += 1
                return task_count

            async def consumer(item):
                await asyncio.sleep(0.01)
                return item

            await production.start(1, 1, producer, consumer)

            # 等待一段时间让任务完成
            await asyncio.sleep(0.1)

            # 停止生产者
            for task in production.producer_tasks:
                task.cancel()

            # 等待队列清空
            done = await production.wait_until_done(timeout=1)
            assert done

            await production.shutdown()

        self.loop.run_until_complete(test())


class TestProductionIntegration(unittest.TestCase):
    """集成测试：测试Production和AsyncProduction的综合使用场景"""

    def test_sync_production_stress_test(self):
        """同步生产者-消费者压力测试"""
        production = Production(queue_size=20)
        counter = {'produced': 0, 'consumed': 0}
        lock = threading.Lock()

        def producer():
            with lock:
                if counter['produced'] >= 50:  # 限制生产数量
                    time.sleep(1)
                    return counter['produced']
                counter['produced'] += 1
                return counter['produced']

        def consumer(item):
            time.sleep(0.001)  # 模拟少量工作
            with lock:
                counter['consumed'] += 1
            return item * 2

        # 添加多个生产者和消费者
        for _i in range(3):
            production.add_producer(producer)
        for _i in range(2):
            production.add_consumer(consumer)

        # 运行较长时间
        time.sleep(1)

        results = production.shutdown()

        # 验证大量任务被处理
        assert len(results) > 10
        assert counter['produced'] > 10
        assert counter['consumed'] > 10

    def test_async_production_stress_test(self):
        """异步生产者-消费者压力测试"""

        async def stress_test():
            production = AsyncProduction(queue_size=50)
            counter = {'produced': 0, 'consumed': 0}

            async def producer():
                if counter['produced'] >= 20:  # 限制生产数量
                    await asyncio.sleep(10)
                    return None

                await asyncio.sleep(0.001)
                counter['produced'] += 1
                return counter['produced']

            async def consumer(item):
                await asyncio.sleep(0.002)
                counter['consumed'] += 1
                return item * 2

            await production.start(2, 2, producer, consumer)

            # 运行较长时间
            await asyncio.sleep(0.5)

            await production.shutdown()

            # 验证大量任务被处理
            assert counter['produced'] > 5
            assert counter['consumed'] > 5

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(stress_test())
        finally:
            try:
                # 清理所有未完成的任务
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            finally:
                loop.close()


def run_sync_test():
    """测试同步生产消费系统"""
    print('\n=== 开始同步生产消费系统测试 ===')

    def producer_function():
        """生产者生成随机数"""
        time.sleep(random.uniform(0.1, 0.5))  # 模拟生产时间
        item = random.randint(1, 100)  # 生成随机数
        print(f'生产者生成: {item}')
        return item

    def consumer_function(item):
        """消费者处理生成的随机数"""
        time.sleep(random.uniform(0.1, 0.5))  # 模拟消费时间
        print(f'消费者消费: {item}')
        # 模拟偶尔的错误情况,测试错误处理
        if item % 7 == 0:
            raise ValueError(f'测试错误: 数字{item}能被7整除')
        return item * 2  # 返回处理结果

    def error_handler(e, item):
        """处理消费过程中的错误"""
        print(f'处理{item}时发生错误: {e}')

    # 创建生产系统实例
    production_system = Production(queue_size=5)
    production_system.set_error_callback(error_handler)

    # 添加生产者和消费者
    for _ in range(3):  # 添加3个生产者
        production_system.add_producer(producer_function)

    for _ in range(2):  # 添加2个消费者
        production_system.add_consumer(consumer_function)

    # 运行一段时间后停止
    print(f'系统启动,当前任务数: {production_system.get_task_count()}')
    time.sleep(2)  # 让生产和消费运行2秒

    # 检查任务状态和统计信息
    print(f'运行中,当前任务数: {production_system.get_task_count()}')
    current_results = production_system.get_result_list()
    print(f'当前已完成的结果数: {len(current_results)}')
    if current_results:
        print(f'当前已完成的部分结果: {current_results[:3]}')

    # 查看统计信息
    stats = production_system.get_stats()
    print(f'系统运行统计: {stats}')

    # 测试单独获取结果
    if not production_system.res_queue.empty():
        single_result = production_system.get_result()
        print(f'单独获取的一个结果: {single_result}')

    # 停止系统并获取结果
    results = production_system.shutdown()
    print(f'测试完成,共处理了{len(results)}个任务')
    print(f'前5个结果: {results[:5] if len(results) >= 5 else results}')


async def run_async_test():
    """测试异步生产消费系统"""
    print('\n=== 开始异步生产消费系统测试 ===')

    async def mock_producer():
        """模拟生产者：生成随机数"""
        await asyncio.sleep(0.1)  # 模拟耗时操作
        item = random.randint(1, 100)  # 生成随机数
        print(f'异步生产者生成: {item}')
        return item

    async def mock_consumer(item):
        """模拟消费者：处理数据"""
        await asyncio.sleep(0.2)  # 模拟耗时操作
        print(f'异步消费者处理: {item}')
        # 模拟偶尔的错误情况,测试错误处理
        if item % 7 == 0:
            raise ValueError(f'测试错误: 数字{item}能被7整除')
        return item * 2

    async def error_handler(e, item):
        """处理异步消费过程中的错误"""
        # 异步错误处理逻辑
        await asyncio.sleep(0.1)  # 模拟异步操作
        print(f'异步处理{item}时发生错误: {e}')

    # 创建异步生产系统
    system = AsyncProduction(queue_size=5)
    await system.set_error_callback(error_handler)

    # 测试重复启动保护
    await system.start(num_producers=2, num_consumers=3, producer_fn=mock_producer, consumer_fn=mock_consumer)

    print('异步系统启动成功')
    # 测试再次启动（应该不会有问题,因为有重复启动保护）
    await system.start(3, 4, mock_producer, mock_consumer)
    print('验证重复启动保护正常工作')

    # 运行一段时间
    await asyncio.sleep(2)  # 运行2秒

    # 等待队列处理完成
    print('等待所有任务处理完成...')
    done = await system.wait_until_done(timeout=3)
    print(f'队列处理{"完成" if done else "超时"}')

    # 停止系统
    await system.shutdown()
    print('异步测试完成')

    # 测试重复停止保护
    await system.shutdown()
    print('验证重复停止保护正常工作')


def run_sync_manager_test():
    """测试同步生产消费管理器"""
    print('\n=== 开始同步生产消费管理器测试 ===')

    def producer():
        """简单的生产者函数"""
        time.sleep(0.1)
        value = random.randint(1, 100)
        print(f'管理器测试 - 生产者生成: {value}')
        return value

    def consumer(item):
        """简单的消费者函数"""
        time.sleep(0.1)
        result = item * 2
        print(f'管理器测试 - 消费者处理: {item} -> {result}')
        return result

    # 创建管理器
    manager = SyncProductionManager(queue_size=10, num_producers=2, num_consumers=3)

    # 初始化并启动系统
    manager.initialize(producer, consumer)

    # 运行一段时间
    time.sleep(2)

    # 查看状态
    print(f'管理器测试 - 当前任务数: {manager.get_task_count()}')
    print(f'管理器测试 - 当前运行状态: {manager.is_running}')

    # 停止系统并获取结果
    results = manager.stop()
    print(f'管理器测试 - 共处理了{len(results)}个任务')

    # 验证系统已停止
    print(f'管理器测试 - 停止后运行状态: {manager.is_running}')


async def run_async_manager_test():
    """测试异步生产消费管理器"""
    print('\n=== 开始异步生产消费管理器测试 ===')

    async def producer():
        """简单的异步生产者函数"""
        await asyncio.sleep(0.1)
        value = random.randint(1, 100)
        print(f'异步管理器测试 - 生产者生成: {value}')
        return value

    async def consumer(item):
        """简单的异步消费者函数"""
        await asyncio.sleep(0.1)
        result = item * 2
        print(f'异步管理器测试 - 消费者处理: {item} -> {result}')
        return result

    # 创建管理器
    manager = AsyncProductionManager(queue_size=10, num_producers=2, num_consumers=3)

    # 初始化并启动系统
    await manager.initialize(producer, consumer)

    # 运行一段时间
    await asyncio.sleep(2)

    # 查看状态
    print(f'异步管理器测试 - 当前运行状态: {manager.is_running}')

    # 停止系统
    await manager.stop(wait_for_completion=True, timeout=3)

    # 验证系统已停止
    print(f'异步管理器测试 - 停止后运行状态: {manager.is_running}')


# 运行同步测试
run_sync_test()

# 运行异步测试
asyncio.run(run_async_test())

# 运行同步管理器测试
run_sync_manager_test()

# 运行异步管理器测试
asyncio.run(run_async_manager_test())

print('\n=== 所有测试完成 ===')

unittest.main()  # verbosity=2)
