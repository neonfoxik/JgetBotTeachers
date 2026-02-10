from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
def get_main_menu(user=None) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📋 Мои задачи", callback_data="tasks"),
        InlineKeyboardButton("➕ Создать задачу", callback_data="create_task")
    )
    markup.add(
        InlineKeyboardButton("📝 Созданные мной", callback_data="my_created_tasks"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )
    
    if user and not user.is_tutorial_finished:
        markup.add(InlineKeyboardButton("🎓 Пройти обучение", callback_data="start_tutorial"))
    
    return markup

main_markup = get_main_menu()
TASK_MANAGEMENT_MARKUP = get_main_menu()
UNIVERSAL_BUTTONS = InlineKeyboardMarkup()
UNIVERSAL_BUTTONS.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
def get_task_actions_markup(task_id: int, task_status: str = None, report_attachments: list = None,
                          is_creator: bool = False, is_assignee: bool = False) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()

    # Для завершенных задач
    if task_status == 'completed':
        markup.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"task_edit_{task_id}"))
        if is_creator:
            markup.add(InlineKeyboardButton("🗑️ Удалить задачу из БД", callback_data=f"task_delete_{task_id}"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        return markup

    # Кнопка прогресса нужна всем (кроме случая ниже, где она добавится парой)
    btn_progress = InlineKeyboardButton("📊 Прогресс", callback_data=f"task_progress_{task_id}")
    
    # 1. Логика для Создателя
    if is_creator:
        if task_status == 'pending_review':
            markup.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"task_confirm_{task_id}"))
            markup.add(InlineKeyboardButton("❌ Отклонить", callback_data=f"task_reject_{task_id}"))
        elif task_status == 'active':
            # Если создатель сам исполнитель, он может сразу завершить
            if is_assignee:
                btn_complete = InlineKeyboardButton("✅ Отметить выполненной", callback_data=f"task_complete_{task_id}")
                markup.add(btn_progress, btn_complete)
            else:
                markup.add(btn_progress)
        else:
             markup.add(btn_progress)

    # 2. Логика для Исполнителя (если он не создатель, у создателя своя верхняя логика)
    elif is_assignee:
        if task_status == 'active':
            btn_close = InlineKeyboardButton("📤 Отправить на проверку", callback_data=f"task_close_{task_id}")
            markup.add(btn_progress, btn_close)
        elif task_status == 'pending_review':
            btn_pending = InlineKeyboardButton("⏳ Ожидает проверки", callback_data=f"task_status_{task_id}")
            markup.add(btn_progress, btn_pending)
        else:
            markup.add(btn_progress)
    
    # Если зашел кто-то другой (вдруг), просто прогресс
    else:
        markup.add(btn_progress)

    # 3. Кнопки редактирования (теперь доступны и создателю, и исполнителю)
    if task_status == 'active' and (is_creator or is_assignee):
        markup.add(InlineKeyboardButton("📋 Добавить подзадачи", callback_data=f"add_subtasks_{task_id}"))
        markup.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"task_edit_{task_id}"))

    # 4. Удаление только для создателя
    if is_creator:
        markup.add(InlineKeyboardButton("🗑️ Удалить задачу из БД", callback_data=f"task_delete_{task_id}"))

    # 5. Вложения отчета
    if report_attachments and len(report_attachments) > 0:
        markup.add(InlineKeyboardButton("📎 Посмотреть вложения отчета", callback_data=f"view_report_attachments_{task_id}"))
    
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

    # Добавляем кнопку "Назад к выбору исполнителя" в начало
    markup.add(InlineKeyboardButton("⬅️ Назад к выбору исполнителя", callback_data="back_to_assignee_selection"))

    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_on_page = users[start_idx:end_idx]
    for user in users_on_page:
        role_emoji = "👑" if user.is_admin else "👨‍🎓"
        markup.add(InlineKeyboardButton(
            f"{role_emoji} {user.get_full_name()}",
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
    
    markup.add(InlineKeyboardButton("⬅️ В меню", callback_data="main_menu"))
    return markup
