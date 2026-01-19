from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
main_markup = InlineKeyboardMarkup()
main_markup.add(
    InlineKeyboardButton("📋 Мои задачи", callback_data="tasks"),
    InlineKeyboardButton("➕ Создать задачу", callback_data="create_task")
)
main_markup.add(InlineKeyboardButton("📝 Созданные мной", callback_data="my_created_tasks"))
TASK_MANAGEMENT_MARKUP = InlineKeyboardMarkup()
UNIVERSAL_BUTTONS = InlineKeyboardMarkup()
UNIVERSAL_BUTTONS.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
def get_task_actions_markup(task_id: int, task_status: str = None, report_attachments: list = None,
                          is_creator: bool = False, is_assignee: bool = False) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()

    # Для завершенных задач показываем только кнопки удаления и возврата в главное меню
    if task_status == 'completed':
        markup.add(InlineKeyboardButton("🗑️ Удалить задачу из БД", callback_data=f"task_delete_{task_id}"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        return markup

    btn1 = InlineKeyboardButton("📊 Прогресс", callback_data=f"task_progress_{task_id}")
    if is_assignee and task_status in ['active', 'pending_review']:
        if task_status == 'active':
            if is_creator:
                btn2 = InlineKeyboardButton("✅ Отметить выполненной", callback_data=f"task_complete_{task_id}")
            else:
                btn2 = InlineKeyboardButton("📤 Отправить на проверку", callback_data=f"task_close_{task_id}")
        else:
            btn2 = InlineKeyboardButton("⏳ Ожидает проверки", callback_data=f"task_status_{task_id}")
        markup.add(btn1, btn2)
    elif is_creator:
        if task_status == 'pending_review':
            markup.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"task_confirm_{task_id}"))
            markup.add(InlineKeyboardButton("❌ Отклонить", callback_data=f"task_reject_{task_id}"))
        else:
            markup.add(btn1)
            markup.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"task_edit_{task_id}"))
    else:
        markup.add(btn1)

    # Кнопка удаления доступна для всех задач, где пользователь имеет права
    if is_creator or is_assignee:
        markup.add(InlineKeyboardButton("🗑️ Удалить задачу из БД", callback_data=f"task_delete_{task_id}"))

    if report_attachments and len(report_attachments) > 0:
        btn_attachments = InlineKeyboardButton("📎 Посмотреть вложения отчета", callback_data=f"view_report_attachments_{task_id}")
        markup.add(btn_attachments)
    return markup
def get_task_confirmation_markup(task_id: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("✅ Подтвердить", callback_data=f"task_confirm_{task_id}")
    btn2 = InlineKeyboardButton("❌ Отклонить", callback_data=f"task_reject_{task_id}")
    markup.add(btn1, btn2)
    return markup
def get_subtask_toggle_markup(task_id: int, subtasks) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    for subtask in subtasks:
        status = "✅" if subtask.is_completed else "⏳"
        markup.add(InlineKeyboardButton(
            f"{status} {subtask.title}",
            callback_data=f"subtask_toggle_{task_id}_{subtask.id}"
        ))
    return markup
def get_user_selection_markup(users, page: int = 0, users_per_page: int = 5) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_on_page = users[start_idx:end_idx]
    for user in users_on_page:
        role_emoji = "👑" if user.is_admin else "👨‍🎓"
        markup.add(InlineKeyboardButton(
            f"{role_emoji} {user.user_name}",
            callback_data=f"select_user_{user.telegram_id}"
        ))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"user_page_{page-1}"))
    # Проверяем тип users - если это QuerySet, используем count(), иначе len()
    # QuerySet имеет метод count() без аргументов, список - нет
    if hasattr(users, 'count') and not isinstance(users, list):
        try:
            total_users = users.count()
        except (TypeError, AttributeError):
            total_users = len(users)
    else:
        total_users = len(users)
    total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"user_page_{page+1}"))
    if nav_buttons:
        markup.add(*nav_buttons)

    return markup
def get_tasks_list_markup(tasks, is_creator_view: bool = False) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    for task in tasks:
        status_emoji = {
            'active': '🔄',
            'pending_review': '⏳',
            'completed': '✅',
            'cancelled': '❌'
        }.get(task.status, '❓')
        btn_text = f"{status_emoji} {task.title}"
        if task.due_date:
            from django.utils import timezone
            if task.due_date < timezone.now() and task.status == 'active':
                btn_text = f"🚨 {task.title}"
        markup.add(InlineKeyboardButton(
            btn_text,
            callback_data=f"task_view_{task.id}_{'creator' if is_creator_view else 'assignee'}"
        ))
    return markup
TASK_MANAGEMENT_MARKUP = InlineKeyboardMarkup()
btn1 = InlineKeyboardButton("📋 Мои задачи", callback_data="tasks")
btn2 = InlineKeyboardButton("➕ Создать задачу", callback_data="create_task")
btn3 = InlineKeyboardButton("📝 Созданные мной", callback_data="my_created_tasks")
TASK_MANAGEMENT_MARKUP.add(btn1, btn2).add(btn3)