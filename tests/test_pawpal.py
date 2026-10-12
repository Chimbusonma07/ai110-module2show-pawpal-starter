"""Tests for the PawPal+ core classes.

Run from the project root with:

    pytest
"""

from pawpal_system import Pet, Task, TaskCategory


def test_mark_complete_changes_task_status():
    """A task starts incomplete and mark_complete() flips it."""
    task = Task("Morning feed", TaskCategory.FEEDING, 10)
    assert task.is_complete is False

    task.mark_complete()

    assert task.is_complete is True


def test_adding_task_increases_pet_task_count():
    """Each add_task() call grows the pet's task list by one."""
    pet = Pet(name="Mochi", species="cat")
    assert len(pet.tasks) == 0

    pet.add_task(Task("Morning feed", TaskCategory.FEEDING, 10))
    assert len(pet.tasks) == 1

    before = len(pet.tasks)
    pet.add_task(Task("Thyroid pill", TaskCategory.MEDICATION, 5))
    assert len(pet.tasks) == before + 1
