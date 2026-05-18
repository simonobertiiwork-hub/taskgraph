"""Кастомные исключения для проекта."""


class TaskGraphException(Exception):
    """Базовое исключение для всех ошибок проекта."""
    pass


class NotFoundError(TaskGraphException):
    """Ресурс не найден (404)."""
    pass


class ConflictError(TaskGraphException):
    """Конфликт версий (409)."""
    pass


class ValidationError(TaskGraphException):
    """Ошибка валидации данных (400)."""
    pass


class DatabaseError(TaskGraphException):
    """Ошибка при работе с БД (500)."""
    pass