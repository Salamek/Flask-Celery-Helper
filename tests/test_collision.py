"""Test single-instance collision."""

import pytest

from flask_celery.exceptions import OtherInstanceError
from flask_celery.lock_manager import LockManager
from tests.instances import celery

PARAMS = [('tests.instances.add', 8), ('tests.instances.mul', 16), ('tests.instances.sub', 0)]


#  def test_wth():
#    """Test wth is going on."""
#    task = celery.tasks['tests.instances.add']
#    task_running = task.apply_async(args=(4, 4))
#    print(task_running.wait(1))


@pytest.mark.parametrize('task_name,expected', PARAMS)
def test_basic(task_name, expected):
    """Test no collision."""
    task = celery.tasks[task_name]
    assert expected == task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)


@pytest.mark.parametrize('task_name,expected', PARAMS)
def test_collision(task_name, expected):
    """Test single-instance collision."""
    manager_instance = list()
    task = celery.tasks[task_name]

    # First run the task and prevent it from removing the lock.
    def new_exit(self, *_):
        print('EXIT CALLED')
        manager_instance.append(self)
        return None
    original_exit = LockManager.__exit__
    setattr(LockManager, '__exit__', new_exit)
    assert expected == task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)
    setattr(LockManager, '__exit__', original_exit)
    assert manager_instance[0].is_already_running is True

    # Now run it again.
    with pytest.raises(OtherInstanceError) as e:
        task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)
    if manager_instance[0].include_args:
        assert str(e.value).startswith('Failed to acquire lock, {0}.args.'.format(task_name))
    else:
        assert 'Failed to acquire lock, {0} already running.'.format(task_name) == str(e.value)
    assert manager_instance[0].is_already_running is True

    # Clean up.
    manager_instance[0].reset_lock()
    assert manager_instance[0].is_already_running is False

    # Once more.
    assert expected == task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)


def test_include_args():
    """Test single-instance collision with task arguments taken into account."""
    manager_instance = list()
    task = celery.tasks['tests.instances.mul']

    # First run the tasks and prevent them from removing the locks.
    def new_exit(self, *_):  # noqa: D401
        """Expected to be run twice."""
        manager_instance.append(self)
        return None
    original_exit = LockManager.__exit__
    setattr(LockManager, '__exit__', new_exit)
    assert 16 == task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)
    assert 20 == task.apply_async(args=(5, 4)).get(disable_sync_subtasks=False)
    setattr(LockManager, '__exit__', original_exit)
    assert manager_instance[0].is_already_running is True
    assert manager_instance[1].is_already_running is True

    # Now run them again.
    with pytest.raises(OtherInstanceError) as e:
        task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)
    assert str(e.value).startswith('Failed to acquire lock, tests.instances.mul.args.')
    assert manager_instance[0].is_already_running is True
    with pytest.raises(OtherInstanceError) as e:
        task.apply_async(args=(5, 4)).get(disable_sync_subtasks=False)
    assert str(e.value).startswith('Failed to acquire lock, tests.instances.mul.args.')
    assert manager_instance[1].is_already_running is True

    # Clean up.
    manager_instance[0].reset_lock()
    assert manager_instance[0].is_already_running is False
    manager_instance[1].reset_lock()
    assert manager_instance[1].is_already_running is False

    # Once more.
    assert 16 == task.apply_async(args=(4, 4)).get(disable_sync_subtasks=False)
    assert 20 == task.apply_async(args=(5, 4)).get(disable_sync_subtasks=False)
