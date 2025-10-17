# !/usr/bin/env python
"""
测试 AsyncThreadPool 结果顺序
"""

from __future__ import annotations

import asyncio
import sys
import time

from nsthread.futures import AsyncThreadPool


def ordered_task(task_id: int) -> int:
    """按顺序返回任务ID的任务，添加随机等待时间"""
    import random

    time.sleep(random.uniform(0.01, 0.1))  # 随机等待时间，增加测试难度
    return task_id


async def ordered_async_task(task_id: int) -> int:
    """按顺序返回任务ID的异步任务，添加随机等待时间"""
    import random

    await asyncio.sleep(random.uniform(0.01, 0.1))  # 随机等待时间，增加测试难度
    return task_id


def test_ordered_sync_tasks():
    """测试同步任务的结果顺序"""
    print('=' * 50)
    print('测试: 同步任务结果顺序')
    print('=' * 50)

    with AsyncThreadPool(max_workers=3) as pool:
        # 提交10个任务
        for i in range(10):
            pool.submit_task(ordered_task, i)

        results = pool.wait_all_completed()

        # 检查结果顺序
        expected_order = list(range(10))
        actual_order = [r.result for r in results]

        print(f'期望顺序: {expected_order}')
        print(f'实际顺序: {actual_order}')

        if actual_order == expected_order:
            print('✅ 同步任务结果顺序正确')
            return True
        print('❌ 同步任务结果顺序错误')
        return False


def test_ordered_async_tasks():
    """测试异步任务的结果顺序"""
    print('\n' + '=' * 50)
    print('测试: 异步任务结果顺序')
    print('=' * 50)

    with AsyncThreadPool(max_workers=3) as pool:
        # 提交10个任务
        for i in range(10):
            pool.submit_task(ordered_async_task, i)

        results = pool.wait_all_completed()
        res = pool.get_results()
        print(f'1111111111111111111111111: {res}')
        # 检查结果顺序
        expected_order = list(range(10))
        actual_order = [r.result for r in results]

        print(f'期望顺序: {expected_order}')
        print(f'实际顺序: {actual_order}')

        if actual_order == expected_order:
            print('✅ 异步任务结果顺序正确')
            return True
        print('❌ 异步任务结果顺序错误')
        return False


def test_ordered_batch_tasks():
    """测试批量任务的结果顺序"""
    print('\n' + '=' * 50)
    print('测试: 批量任务结果顺序')
    print('=' * 50)

    with AsyncThreadPool(max_workers=3) as pool:
        # 批量提交10个任务
        tasks = list(range(10))
        pool.submit_tasks(ordered_task, tasks)

        results = pool.wait_all_completed()
        res = pool.get_results()
        print(f'1111111111111111111111111: {res}')
        # 检查结果顺序
        expected_order = list(range(10))
        actual_order = [r.result for r in results]

        print(f'期望顺序: {expected_order}')
        print(f'实际顺序: {actual_order}')

        if actual_order == expected_order:
            print('✅ 批量任务结果顺序正确')
            return True
        print('❌ 批量任务结果顺序错误')
        return False


def test_success_and_error_count():
    """测试正常结果和错误数量的判定"""
    print('\n' + '=' * 50)
    print('测试: 正常结果和错误数量判定')
    print('=' * 50)

    def mixed_task(task_id: int) -> int:
        """混合任务：偶数ID成功，奇数ID抛出异常"""
        if task_id % 2 == 1:
            raise ValueError(f'任务 {task_id} 故意抛出异常')
        return task_id

    with AsyncThreadPool(max_workers=4) as pool:
        # 提交10个混合任务
        for i in range(10):
            pool.submit_task(mixed_task, i)

        results = pool.wait_all_completed()
        res = pool.get_results()
        print(f'1111111111111111111111111: {res}')
        # 统计成功和失败的数量
        success_count = sum(1 for r in results if r.success)
        error_count = sum(1 for r in results if not r.success)

        print(f'总任务数: {len(results)}')
        print(f'成功任务数: {success_count}')
        print(f'失败任务数: {error_count}')

        # 验证结果
        expected_success = 5  # 偶数ID: 0,2,4,6,8
        expected_error = 5  # 奇数ID: 1,3,5,7,9

        # 检查成功任务的结果
        success_results = [r for r in results if r.success]
        success_values = [r.result for r in success_results]
        expected_success_values = [0, 2, 4, 6, 8]

        # 检查失败任务的错误信息
        error_results = [r for r in results if not r.success]
        error_messages = [str(r.error) for r in error_results]

        print(f'成功任务结果: {success_values}')
        print(f'期望成功结果: {expected_success_values}')
        print(f'失败任务错误: {error_messages}')

        # 断言验证
        if success_count == expected_success and error_count == expected_error and set(success_values) == set(expected_success_values):
            print('✅ 正常结果和错误数量判定正确')
            return True
        print('❌ 正常结果和错误数量判定错误')
        print(f'期望成功数: {expected_success}, 实际: {success_count}')
        print(f'期望失败数: {expected_error}, 实际: {error_count}')
        return False


def run_all_tests():
    """运行所有顺序测试"""
    print('AsyncThreadPool 结果顺序测试开始')

    tests = [
        test_ordered_sync_tasks,
        test_ordered_async_tasks,
        test_ordered_batch_tasks,
        test_success_and_error_count,
    ]

    results = []
    for test_func in tests:
        try:
            success = test_func()
            results.append((test_func.__name__, success))
        except Exception as e:
            print(f'❌ 测试 {test_func.__name__} 发生异常: {e}')
            results.append((test_func.__name__, False))

    # 输出测试结果汇总
    print('\n' + '=' * 50)
    print('顺序测试结果汇总:')
    print('=' * 50)
    passed = 0
    for test_name, success in results:
        status = '✅ 通过' if success else '❌ 失败'
        print(f'{test_name}: {status}')
        if success:
            passed += 1

    print(f'\n总计: {passed}/{len(results)} 个顺序测试通过')
    return passed == len(results)


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
