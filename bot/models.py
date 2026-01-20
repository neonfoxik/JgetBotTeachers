from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
class User(models.Model):
    telegram_id = models.CharField(
        primary_key=True,
        max_length=50,
        verbose_name='Telegram ID'
    )
    user_name = models.CharField(
        max_length=100,
        verbose_name='Имя пользователя'
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Имя',
        help_text='Имя пользователя из Telegram'
    )
    is_admin = models.BooleanField(
        default=False,
        verbose_name='Администратор'
    )
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        verbose_name='Часовой пояс'
    )
    is_tutorial_finished = models.BooleanField(
        default=False,
        verbose_name='Обучение пройдено'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )
    def __str__(self):
        return f"{self.user_name} ({'Админ' if self.is_admin else 'Учитель'})"
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
class Task(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активная'),
        ('pending_review', 'Ожидает подтверждения'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
    ]
    title = models.CharField(
        max_length=200,
        verbose_name='Название задачи',
        help_text='Краткое название задачи'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание',
        help_text='Подробное описание задачи'
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name='Создатель'
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
        verbose_name='Исполнитель'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус'
    )
    progress = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Прогресс',
        help_text='Например: "2/5" для 2 выполненных из 5 подзадач'
    )
    due_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Срок выполнения'
    )
    attachments = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name='Вложения',
        help_text='Список URL вложений (фото, файлы)'
    )
    report_text = models.TextField(
        blank=True,
        null=True,
        verbose_name='Текст отчета',
        help_text='Текст отчета исполнителя при закрытии задачи'
    )
    report_attachments = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name='Вложения отчета',
        help_text='Вложения отчета исполнителя'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    closed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата закрытия'
    )
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    def clean(self):
        if self.creator == self.assignee and self.status == 'active':
            pass
        elif self.creator != self.assignee and self.status == 'pending_review':
            if not self.report_text:
                raise ValidationError('Для задач в статусе "Ожидает подтверждения" требуется текст отчета')
    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.closed_at:
            self.closed_at = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)
    def get_progress_percentage(self):
        if not self.progress or '/' not in self.progress:
            return 0
        try:
            completed, total = map(int, self.progress.split('/'))
            return int((completed / total) * 100) if total > 0 else 0
        except (ValueError, ZeroDivisionError):
            return 0
    def update_progress(self):
        subtasks = self.subtasks.all()
        if subtasks:
            completed_count = subtasks.filter(is_completed=True).count()
            total_count = subtasks.count()
            self.progress = f"{completed_count}/{total_count}"
        else:
            self.progress = None
        self.save()
    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']
class Subtask(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='subtasks',
        verbose_name='Задача'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Название подзадачи'
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name='Выполнена'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата выполнения'
    )
    def __str__(self):
        status = "✅" if self.is_completed else "⏳"
        return f"{status} {self.title}"
    def save(self, *args, **kwargs):
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.is_completed and self.completed_at:
            self.completed_at = None
        super().save(*args, **kwargs)
        self.task.update_progress()
    class Meta:
        verbose_name = 'Подзадача'
        verbose_name_plural = 'Подзадачи'
        ordering = ['created_at']
class UserState(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='state',
        verbose_name='Пользователь'
    )
    state = models.CharField(
        max_length=50,
        verbose_name='Текущее состояние'
    )
    data = models.JSONField(
        default=dict,
        verbose_name='Данные состояния'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    def __str__(self):
        return f"State for {self.user.user_name}: {self.state}"
    class Meta:
        verbose_name = 'Состояние пользователя'
        verbose_name_plural = 'Состояния пользователей'
class TaskComment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Задача'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Автор'
    )
    text = models.TextField(
        verbose_name='Текст комментария'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

class TaskHistory(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Задача'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Кто изменил'
    )
    action = models.CharField(
        max_length=200,
        verbose_name='Действие'
    )
    old_value = models.TextField(
        blank=True,
        null=True,
        verbose_name='Старое значение'
    )
    new_value = models.TextField(
        blank=True,
        null=True,
        verbose_name='Новое значение'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата изменения'
    )

    class Meta:
        verbose_name = 'История задачи'
        verbose_name_plural = 'История задач'
        ordering = ['-created_at']
