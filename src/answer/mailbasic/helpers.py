


from src.orm.mail import update_mail_field, delete_mails


def mark_mail_read(commander_id: int, mail_id: int) -> bool:
    try:
        update_mail_field(commander_id, mail_id, "read", True)
        return True
    except Exception:
        return False


def delete_mail(commander_id: int, mail_id: int) -> bool:
    try:
        delete_mails(commander_id, [mail_id])
        return True
    except Exception:
        return False
