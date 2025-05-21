class ParkingRouter:
    """
    A router to control database operations for parking-related models.
    """
    parking_models = ['spotini', 'subrouterini', 'deviceini', 'matchpanel', 'panelini', 'siteconfigeration']

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'app' and model._meta.model_name in self.parking_models:
            return 'parking'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'app' and model._meta.model_name in self.parking_models:
            return 'parking'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'parking':
            # 允许所有指定的模型迁移到 parking 数据库
            return app_label == 'app' and model_name in self.parking_models
        elif db == 'default':
            # 其他所有模型都迁移到默认数据库
            return not (app_label == 'app' and model_name in self.parking_models)
        return None
