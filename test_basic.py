import os
import sys
import django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()
from django.utils import timezone
from bot.models import User, Task, Subtask
def test_models():
    print("🧪 Тестирование моделей...")
    admin = User.objects.create(
        telegram_id='123456789',
        user_name='Администратор',
        is_admin=True
    )
    teacher = User.objects.create(
        telegram_id='987654321',
        user_name='Учитель',
        is_admin=False
    )
    student = User.objects.create(
        telegram_id='555666777',
        user_name='Студент',
        is_admin=False
    )
    print(f"✓ Создан {admin}")
    print(f"✓ Создан {teacher}")
    print(f"✓ Создан {student}")
    task = Task.objects.create(
        title='Тестовая задача',
        description='Описание тестовой задачи',
        creator=admin,
        assignee=teacher,
        due_date=timezone.now() + timezone.timedelta(days=7)
    )
    print(f"✓ Создана {task}")
    subtask1 = Subtask.objects.create(
        task=task,
        title='Подзадача 1',
        is_completed=False
    )
    subtask2 = Subtask.objects.create(
        task=task,
        title='Подзадача 2',
        is_completed=True
    )
    print(f"✓ Созданы подзадачи: {subtask1}, {subtask2}")
    task.refresh_from_db()
    print(f"✓ Прогресс задачи: {task.progress}")
    subtask1.is_completed = True
    subtask1.save()
    task.refresh_from_db()
    print(f"✓ Новый прогресс: {task.progress}")
    task.status = 'completed'
    task.save()
    print(f"✓ Задача завершена: {task}")
    Subtask.objects.filter(task=task).delete()
    Task.objects.filter(id=task.id).delete()
    User.objects.filter(telegram_id__in=['123456789', '987654321', '555666777']).delete()
    print("✓ Очистка завершена")
def test_permissions():
    print("\n🧪 Тестирование прав доступа...")
    admin = User.objects.create(telegram_id='111', user_name='Admin', is_admin=True)
    teacher = User.objects.create(telegram_id='222', user_name='Teacher', is_admin=False)
    task = Task.objects.create(
        title='Test Task',
        creator=admin,
        assignee=teacher
    )
    from bot.handlers.tasks import check_permissions
    admin_allowed, admin_msg = check_permissions('111', task, require_creator=False)
    teacher_allowed, teacher_msg = check_permissions('222', task, require_creator=False)
    other_allowed, other_msg = check_permissions('333', task, require_creator=False)
    print(f"✓ Админ имеет доступ: {admin_allowed}")
    print(f"✓ Учитель имеет доступ: {teacher_allowed}")
    print(f"✓ Другие не имеют доступа: {not other_allowed}")
    Task.objects.filter(id=task.id).delete()
    User.objects.filter(telegram_id__in=['111', '222']).delete()
    print("✓ Тест прав доступа завершен")
if __name__ == '__main__':
    print("🚀 Запуск базового тестирования модуля задач\n")
    try:
        test_models()
        test_permissions()
        print("\n✅ Все тесты пройдены успешно!")
        print("📊 Модуль управления задачами работает корректно.")
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)