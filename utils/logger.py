import logging
import sys
import structlog


def configure_logger():
    # 🎯 توحيد اللوجز: توجيه الـ Standard Logging للعمل عبر قنوات Structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars, # دمج ميتاداتا المتغيرات لحظياً
            structlog.processors.add_log_level,     # إضافة حقل الـ Level (INFO, ERROR...)
            structlog.processors.TimeStamper(fmt="iso", utc=True), # تواريخ موحدة بـ الـ UTC العالمي
            structlog.processors.StackInfoRenderer(), # الحفاظ على الـ Stack Trace كامل عند الكراش
            structlog.processors.format_exc_info,    # هندسة وعرض تفاصيل الـ Exceptions
            structlog.processors.JSONRenderer(),     # المخرجات النهائية كـ JSON نقي للـ Cloud Containers
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# تشغيل التهيئة فور استدعاء المكتبة
configure_logger()


def get_logger(name: str):
    return structlog.get_logger(name)