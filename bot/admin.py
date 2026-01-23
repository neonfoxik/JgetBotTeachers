from django.contrib import admin
from .models import User, Task, Subtask, UserState, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'get_users_count', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    filter_horizontal = ()
    
    def get_users_count(self, obj):
        return obj.users.count()
    get_users_count.short_description = 'Количество пользователей'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'get_telegram_handle', 'first_name', 'last_name', 'is_admin', 'get_roles', 'timezone')
    list_editable = ('first_name', 'last_name')
    search_fields = ('telegram_id', 'user_name', 'first_name', 'last_name')
    list_filter = ('is_admin', 'timezone', 'roles')
    readonly_fields = ('telegram_id',)
    filter_horizontal = ('roles',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id', 'user_name', 'first_name', 'last_name')
        }),
        ('Настройки', {
            'fields': ('is_admin', 'timezone')
        }),
        ('Роли', {
            'fields': ('roles',)
        }),
    )

    def get_telegram_handle(self, obj):
        if obj.user_name and not obj.user_name.startswith('user_') and obj.user_name != obj.telegram_id:
            return f"@{obj.user_name}"
        return "—"
    get_telegram_handle.short_description = 'TG Handle'
    
    def get_roles(self, obj):
        return ", ".join([role.name for role in obj.roles.all()]) or "—"
    get_roles.short_description = 'Роли'
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'assignee', 'assigned_role', 'status', 'progress', 'due_date', 'created_at')
    search_fields = ('title', 'description', 'creator__user_name', 'assignee__user_name')
    list_filter = ('status', 'due_date', 'created_at', 'creator', 'assignee', 'assigned_role')
    readonly_fields = ('created_at', 'updated_at', 'closed_at', 'id')
    ordering = ('-created_at',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'creator', 'assignee', 'assigned_role')
        }),
        ('Статус и прогресс', {
            'fields': ('status', 'progress', 'due_date', 'notification_interval', 'last_notified_at')
        }),
        ('Отчет', {
            'fields': ('report_text', 'report_attachments'),
            'classes': ('collapse',)
        }),
        ('Вложения', {
            'fields': ('attachments',),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creator', 'assignee')
@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'title', 'is_completed', 'completed_at', 'created_at')
    search_fields = ('title', 'task__title')
    list_filter = ('is_completed', 'created_at', 'completed_at')
    readonly_fields = ('created_at', 'completed_at', 'id')
    ordering = ('-created_at',)
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('task')

@admin.register(UserState)
class UserStateAdmin(admin.ModelAdmin):
    list_display = ('get_user_name', 'state', 'updated_at')
    search_fields = ('state',)
    list_filter = ('state', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-updated_at',)
    raw_id_fields = ('user',)  # Используем raw_id_fields вместо select_related
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Состояние', {
            'fields': ('state', 'data')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_user_name(self, obj):
        return obj.user.user_name if obj.user else 'N/A'
    get_user_name.short_description = 'Пользователь'
    get_user_name.admin_order_field = 'user__user_name'

    def get_queryset(self, request):
        # Убрали select_related, используем raw_id_fields
        return super().get_queryset(request)