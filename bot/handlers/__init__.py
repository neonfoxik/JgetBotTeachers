# Импорты из новых модулей
from .commands import (
    start_command, tasks_command,
    close_task_command, task_progress_command, debug_command,
    tasks_callback
)
from .tasks import (
    create_task_command, create_task_callback,
    my_created_tasks_command, my_created_tasks_callback
)
from .task_actions import (
    task_view_callback, task_progress_callback, task_complete_callback,
    task_confirm_callback, task_reject_callback, subtask_toggle_callback,
    task_delete_callback, confirm_delete_callback, task_status_callback,
    task_close_callback, view_task_attachments_callback
)
from .task_creation import (
    handle_task_creation_messages, skip_description_callback, skip_due_date_callback,
    assign_to_creator_callback, assign_to_me_callback, choose_user_from_list_callback,
    add_subtask_callback, cancel_subtask_input_callback, clear_subtasks_callback, finish_subtasks_callback,
    clear_attachments_callback, finish_attachments_callback,
    skip_assignee_callback, choose_assignee_callback,
    user_page_callback, select_user_callback, back_to_assignee_selection_callback,
    back_to_assignee_type_callback, cancel_task_creation_callback,
    select_notification_interval_callback, skip_notification_interval_callback,
    back_to_calendar_callback, back_to_notifications_callback, 
    back_to_subtasks_callback, back_to_description_callback, back_to_attachments_callback,
    confirm_cancel_task_callback, actually_cancel_task_callback, resume_task_callback
)
from .role_handlers import (
    choose_role_from_list_callback, select_role_callback
)
from .task_editing import (
    task_edit_callback, edit_title_callback, edit_description_callback,
    edit_assignee_callback, edit_due_date_callback, edit_notification_interval_callback,
    assignee_page_callback, change_assignee_callback, add_subtasks_callback, reopen_task_callback
)
from .reports import (
    handle_task_report, view_report_attachments_callback,
    handle_task_comment, task_comment_callback,
    finish_report_callback, clear_report_attachments_callback
)
from .main import (
    show_task_progress, tasks_back_callback, main_menu_callback
)
from .commands import tasks_command_logic
from .calendar import process_calendar_callback 
from .tutorial import start_tutorial_callback, skip_tutorial_callback
from .registration import handle_registration_input
from .profile import (
    profile_callback, profile_edit_info_menu_callback,
    profile_edit_first_name_callback, profile_edit_last_name_callback,
    profile_edit_work_hours_callback, handle_profile_input
)