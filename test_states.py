import os
import sys
import django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()
from bot.handlers.tasks import get_user_state, set_user_state, clear_user_state
from bot.models import User
def test_user_states():
    print("🧪 Тестирование функций состояний пользователей...")
    user, created = User.objects.get_or_create(
        telegram_id='test123',
        defaults={'user_name': 'Test User'}
    )
    print(f"✓ Создан тестовый пользователь: {user}")
    test_state = {
        'state': 'waiting_task_title',
        'title': 'Тестовая задача'
    }
    set_user_state('test123', test_state)
    print("✓ Установлено состояние пользователя")
    retrieved_state = get_user_state('test123')
    print(f"✓ Получено состояние: {retrieved_state}")
    assert retrieved_state['state'] == 'waiting_task_title'
    assert retrieved_state['title'] == 'Тестовая задача'
    print("✓ Состояние корректно сохранено и получено")
    updated_state = retrieved_state.copy()
    updated_state['state'] = 'waiting_task_description'
    updated_state['description'] = 'Тестовое описание'
    set_user_state('test123', updated_state)
    retrieved_updated = get_user_state('test123')
    assert retrieved_updated['state'] == 'waiting_task_description'
    assert retrieved_updated['description'] == 'Тестовое описание'
    print("✓ Состояние корректно обновлено")
    clear_user_state('test123')
    empty_state = get_user_state('test123')
    assert empty_state == {}
    print("✓ Состояние корректно очищено")
    user.delete()
    print("✓ Тестовый пользователь удален")
if __name__ == '__main__':
    print("🚀 Запуск тестирования состояний пользователей\n")
    try:
        test_user_states()
        print("\n✅ Все тесты функций состояний пройдены успешно!")
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)