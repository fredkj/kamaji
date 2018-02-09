# -*- coding: utf-8 -*-

from django.core.mail.backends import smtp

from fabric.models import Setting


class KamajiEmailBackend(smtp.EmailBackend):
    """
    The KamajiEmailBackend is just like the default SMTP EmailBackend but
    fetches settings from the settings endpoint in the API.
    """
    def __init__(self, *args, **kwargs):
        setting = Setting.objects.get(setting='SMTPRelaySetting')
        super(KamajiEmailBackend, self).__init__(
            *args,
            host=setting.smtp_host,
            use_ssl=setting.connection_security == 'ssl',
            use_tls=setting.connection_security == 'tls',
            port=setting.smtp_port,
            **kwargs
        )
