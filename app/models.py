from django.db import models

# Create your models here.
class SpotIni(models.Model):
    spot_id = models.CharField(max_length=30, verbose_name="车位号", unique=True)
    locate = models.CharField(max_length=60, verbose_name="车位描述", blank=True, null=True)

    class Meta:
        app_label = 'app'
        db_table = 'spot_ini'
        verbose_name = verbose_name_plural = "车位记录"

    def __str__(self):
        return self.spot_id

class SubrouterIni(models.Model):
    mac = models.CharField(max_length=12, verbose_name="子路由号", unique=True)
    node_num = models.IntegerField(verbose_name="设备数量", blank=True, null=True)
    name = models.CharField(max_length=60, verbose_name="子路由描述", blank=True, null=True)
    ver = models.CharField(max_length=8, verbose_name="软件版本", blank=True, null=True)

    class Meta:
        app_label = 'app'
        db_table = 'subrouter_ini'
        verbose_name = verbose_name_plural = "子路由记录"

    def __str__(self):
        return self.mac

class PanelIni(models.Model):
    mac = models.CharField(max_length=12, verbose_name="引导屏地址", unique=True)
    section = models.IntegerField(verbose_name="显示区域", blank=True, null=True)
    name = models.CharField(max_length=60, verbose_name="引导屏描述", blank=True, null=True)
    ver = models.CharField(max_length=8, verbose_name="软件版本", blank=True, null=True)

    class Meta:
        app_label = 'app'
        db_table = 'panel_ini'
        verbose_name = verbose_name_plural = "引导屏记录"

    def __str__(self):
        return self.mac

class DeviceIni(models.Model):
    mac_subrouter = models.CharField(max_length=12, verbose_name="子路由号")
    node_mac = models.CharField(max_length=12, verbose_name="设备地址", unique=True)
    sort = models.CharField(max_length=4, verbose_name="设备短地址", blank=True, null=True)
    status = models.CharField(max_length=2, verbose_name="设备状态", blank=True, null=True)
    spot_num = models.IntegerField(verbose_name="对应车位数量", blank=True, null=True)
    spot_l = models.CharField(max_length=30, verbose_name="左车位号", blank=True, null=True)
    spot_m = models.CharField(max_length=30, verbose_name="中车位号", blank=True, null=True)
    spot_r = models.CharField(max_length=30, verbose_name="右车位号", blank=True, null=True)
    cut_lx = models.IntegerField(verbose_name="左车位x坐标", blank=True, null=True)
    cut_ly = models.IntegerField(verbose_name="左车位y坐标", blank=True, null=True)
    cut_mx = models.IntegerField(verbose_name="中车位x坐标", blank=True, null=True)
    cut_my = models.IntegerField(verbose_name="中车位y坐标", blank=True, null=True)
    cut_rx = models.IntegerField(verbose_name="右车位x坐标", blank=True, null=True)
    cut_ry = models.IntegerField(verbose_name="右车位y坐标", blank=True, null=True)
    pic_sizex = models.IntegerField(verbose_name="图片尺寸x", blank=True, null=True)
    pic_sizey = models.IntegerField(verbose_name="图片尺寸y", blank=True, null=True)
    brightness = models.IntegerField(verbose_name="亮度", blank=True, null=True)
    ver = models.CharField(max_length=8, verbose_name="软件版本", blank=True, null=True)
    plate_l = models.CharField(max_length=30, verbose_name="左车位车牌号", blank=True, null=True)
    plate_m = models.CharField(max_length=30, verbose_name="中车位车牌号", blank=True, null=True)
    plate_r = models.CharField(max_length=30, verbose_name="右车位车牌号", blank=True, null=True)
    plate_lx = models.IntegerField(verbose_name="左车牌x坐标", blank=True, null=True)
    plate_ly = models.IntegerField(verbose_name="左车牌y坐标", blank=True, null=True)
    plate_mx = models.IntegerField(verbose_name="中车牌x坐标", blank=True, null=True)
    plate_my = models.IntegerField(verbose_name="中车牌y坐标", blank=True, null=True)
    plate_rx = models.IntegerField(verbose_name="右车牌x坐标", blank=True, null=True)
    plate_ry = models.IntegerField(verbose_name="右车牌y坐标", blank=True, null=True)

    class Meta:
        app_label = 'app'
        db_table = 'device_ini'
        verbose_name = verbose_name_plural = "设备记录"

    def __str__(self):
        return self.node_mac
    
class MatchPanel(models.Model):
    mac = models.ForeignKey(
        PanelIni,
        to_field='mac',
        on_delete=models.CASCADE,
        verbose_name="引导屏地址"
    )
    section = models.IntegerField(verbose_name="显示区域", blank=True, null=True)
    spot_id = models.ForeignKey(
        SpotIni,
        to_field='spot_id',
        on_delete=models.CASCADE,
        verbose_name="车位号",
        blank=False,
        null=False
    )

    class Meta:
        app_label = 'app'
        db_table = 'match_panel'
        verbose_name = verbose_name_plural = "车位引导屏匹配"

    def __str__(self):
        return f"{self.mac} - {self.spot_id}"

class SiteConfigeration(models.Model):
    company_name = models.CharField(max_length=255, unique=True, default="My Company")
    version = models.CharField(max_length=20, default="1.0.0")
    development_date = models.CharField(max_length=20, blank=True, null=True, help_text="date")
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Configuration name")
    server = models.CharField(max_length=255, blank=True, null=True, default="120.24.111.243", help_text="Server address")
    user = models.CharField(max_length=255, blank=True, null=True, help_text="User name")
    password = models.CharField(max_length=255, blank=True, null=True, help_text="Password for authentication")
    send = models.CharField(max_length=255, blank=True, null=True, default="vchippub1", help_text="send name")
    read = models.CharField(max_length=255, blank=True, null=True, default="vchipsub1", help_text="read name")

    class Meta:
        app_label = 'app'  # 确保是正确的应用标签
        db_table = 'site_configeration'
        verbose_name = verbose_name_plural = "站点配置"

    def save(self, *args, **kwargs):
        # 确保数据库中只有一个实例
        if not self.pk and SiteConfigeration.objects.exists():
            raise ValueError("There can be only one SiteConfiguration instance.")
        return super(SiteConfigeration, self).save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        instance = cls.objects.first()
        if not instance:
            instance = cls.objects.create()
        return instance

    def __str__(self):
        return f"{self.company_name} - Version: {self.version}"
