"""
Configuration Management Module
Handles loading, saving, and managing user preferences.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import json
from dataclasses import dataclass, asdict, field

from .paths import DATA


@dataclass
class TranscriptionConfig:
    """Transcription settings"""
    model_size: str = "base"
    language: str = "en"
    fast_mode: bool = True
    vad_filter: bool = False
    compute_type: str = "int8"
    beam_size: int = 1


@dataclass
class SemanticSearchConfig:
    """Semantic search settings"""
    auto_index_enabled: bool = True
    chunk_size: int = 200
    chunk_overlap: int = 40
    use_embeddings: bool = True


@dataclass
class LLMConfig:
    """LLM settings"""
    ollama_path: Optional[str] = None
    default_model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class UIConfig:
    """UI preferences"""
    theme: str = "dark"
    default_view: str = "home"
    show_advanced_options: bool = False


@dataclass
class AppConfig:
    """Main application configuration"""
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    semantic_search: SemanticSearchConfig = field(default_factory=SemanticSearchConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    version: str = "1.0"


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = DATA / "config.json"
        self.config_path = config_path
        self.config = self.load()
    
    def load(self) -> AppConfig:
        """Load configuration from file or create default"""
        if not self.config_path.exists():
            return AppConfig()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruct dataclasses
            config = AppConfig(
                transcription=TranscriptionConfig(**data.get('transcription', {})),
                semantic_search=SemanticSearchConfig(**data.get('semantic_search', {})),
                llm=LLMConfig(**data.get('llm', {})),
                ui=UIConfig(**data.get('ui', {})),
                version=data.get('version', '1.0')
            )
            return config
        
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            return AppConfig()
    
    def save(self, config: Optional[AppConfig] = None) -> bool:
        """Save configuration to file"""
        if config is not None:
            self.config = config
        
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict
            data = {
                'transcription': asdict(self.config.transcription),
                'semantic_search': asdict(self.config.semantic_search),
                'llm': asdict(self.config.llm),
                'ui': asdict(self.config.ui),
                'version': self.config.version
            }
            
            # Write to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        
        except Exception as e:
            print(f"Error: Failed to save config to {self.config_path}: {e}")
            return False
    
    def update_transcription(self, **kwargs) -> bool:
        """Update transcription settings"""
        for key, value in kwargs.items():
            if hasattr(self.config.transcription, key):
                setattr(self.config.transcription, key, value)
        return self.save()
    
    def update_semantic_search(self, **kwargs) -> bool:
        """Update semantic search settings"""
        for key, value in kwargs.items():
            if hasattr(self.config.semantic_search, key):
                setattr(self.config.semantic_search, key, value)
        return self.save()
    
    def update_llm(self, **kwargs) -> bool:
        """Update LLM settings"""
        for key, value in kwargs.items():
            if hasattr(self.config.llm, key):
                setattr(self.config.llm, key, value)
        return self.save()
    
    def update_ui(self, **kwargs) -> bool:
        """Update UI settings"""
        for key, value in kwargs.items():
            if hasattr(self.config.ui, key):
                setattr(self.config.ui, key, value)
        return self.save()
    
    def reset_to_defaults(self) -> bool:
        """Reset all settings to defaults"""
        self.config = AppConfig()
        return self.save()
    
    def export_config(self, path: Path) -> bool:
        """Export config to a specific path"""
        try:
            data = {
                'transcription': asdict(self.config.transcription),
                'semantic_search': asdict(self.config.semantic_search),
                'llm': asdict(self.config.llm),
                'ui': asdict(self.config.ui),
                'version': self.config.version
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False
    
    def import_config(self, path: Path) -> bool:
        """Import config from a specific path"""
        if not path.exists():
            return False
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.config = AppConfig(
                transcription=TranscriptionConfig(**data.get('transcription', {})),
                semantic_search=SemanticSearchConfig(**data.get('semantic_search', {})),
                llm=LLMConfig(**data.get('llm', {})),
                ui=UIConfig(**data.get('ui', {})),
                version=data.get('version', '1.0')
            )
            return self.save()
        except Exception as e:
            print(f"Error importing config: {e}")
            return False


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global config manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> AppConfig:
    """Get the current configuration"""
    return get_config_manager().config


def save_config() -> bool:
    """Save the current configuration"""
    return get_config_manager().save()
