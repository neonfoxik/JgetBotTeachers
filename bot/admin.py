from django.contrib import admin
from .models import User, Task, Subtask
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'user_name', 'is_admin', 'timezone')
    search_fields = ('telegram_id', 'user_name')
    list_filter = ('is_admin',)
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'assignee', 'status', 'due_date', 'created_at')
    search_fields = ('title', 'creator__user_name', 'assignee__user_name')
    list_filter = ('status', 'due_date', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'closed_at')
    ordering = ('-created_at',)
@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'title', 'is_completed', 'created_at')
    search_fields = ('title', 'task__title')
    list_filter = ('is_completed', 'created_at')
    readonly_fields = ('created_at', 'completed_at')