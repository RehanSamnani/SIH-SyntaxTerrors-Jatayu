from pydantic_settings import BaseSettings, SettingsConfigDict

class DroneSettings(BaseSettings):
    MAX_PAYLOAD_GRAMS: float = 5000.0  # 5kg default max payload
    
    model_config = SettingsConfigDict(env_prefix='DRONE_')

drone_settings = DroneSettings()