class GlobalSettingsService:
    def __init__(self, repo):
        self.repo = repo

    async def get_settings(self):
        return await self.repo.get_settings()

    async def save_settings(self, settings):
        return await self.repo.update_settings(settings)
