from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Role(models.Model):
    """Модель роли для группировки пользователей"""
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название роли'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание роли'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'
        ordering = ['name']


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
        help_text='Имя пользователя'
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Фамилия',
        help_text='Фамилия пользователя'
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
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='users',
        verbose_name='Роли'
    )
    
    def get_full_name(self):
        """Возвращает полное имя пользователя"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        
        # Если имен нет, пробуем user_name. Если это ID или системное 'user_', возвращаем ID
        if self.user_name:
            if self.user_name.startswith('user_'):
                return f"ID {self.telegram_id}"
            return self.user_name
        return f"ID {self.telegram_id}"
    
    def __str__(self):
        return f"{self.get_full_name()} ({'Админ' if self.is_admin else 'Учитель'})"
    
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
        verbose_name='Исполнитель',
        blank=True,
        null=True,
        help_text='Конкретный исполнитель задачи'
    )
    assigned_role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
        verbose_name='Назначено роли',
        blank=True,
        null=True,
        help_text='Роль, которой назначена задача (все пользователи с этой ролью имеют доступ)'
    )
    notification_interval = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Интервал напоминаний (мин)',
        help_text='Интервал отправки напоминаний о задаче. Если не указано, напоминания не отправляются.'
    )
    last_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата последнего уведомления'
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
        # Проверяем, что задача назначена либо пользователю, либо роли, но не обоим сразу
        if self.assignee and self.assigned_role:
            raise ValidationError('Задача не может быть назначена одновременно пользователю и роли')
        if not self.assignee and not self.assigned_role:
            raise ValidationError('Задача должна быть назначена либо пользователю, либо роли')
        
        # Проверка для задач в статусе "Ожидает подтверждения"
        if self.status == 'pending_review':
            if self.assignee and self.creator != self.assignee:
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
    
    def get_assignees(self):
        """Возвращает список всех пользователей, которые имеют доступ к задаче"""
        if self.assignee:
            # Задача назначена конкретному пользователю
            return [self.assignee]
        elif self.assigned_role:
            # Задача назначена роли - возвращаем всех пользователей с этой ролью
            return list(self.assigned_role.users.all())
        return []
    
    def has_access(self, user):
        """Проверяет, имеет ли пользователь доступ к задаче"""
        # Создатель всегда имеет доступ
        if self.creator == user:
            return True
        # Если задача назначена конкретному пользователю
        if self.assignee and self.assignee == user:
            return True
        # Если задача назначена роли, проверяем наличие роли у пользователя
        if self.assigned_role and user.roles.filter(id=self.assigned_role.id).exists():
            return True
        return False
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
