from django.contrib import admin
from .models import User, Task, Subtask, UserState
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'user_name', 'first_name', 'last_name', 'is_admin', 'timezone')
    list_editable = ('first_name', 'last_name')
    search_fields = ('telegram_id', 'user_name', 'first_name', 'last_name')
    list_filter = ('is_admin', 'timezone')
    readonly_fields = ('telegram_id',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id', 'user_name', 'first_name', 'last_name')
        }),
        ('Настройки', {
            'fields': ('is_admin', 'timezone')
        }),
    )
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'assignee', 'status', 'progress', 'due_date', 'created_at')
    search_fields = ('title', 'description', 'creator__user_name', 'assignee__user_name')
    list_filter = ('status', 'due_date', 'created_at', 'creator', 'assignee')
    readonly_fields = ('created_at', 'updated_at', 'closed_at', 'id')
    ordering = ('-created_at',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'creator', 'assignee')
        }),
        ('Статус и прогресс', {
            'fields': ('status', 'progress', 'due_date')
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