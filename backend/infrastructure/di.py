from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DIContainer:
    """
    A lightweight Dependency Injection Container/Registry.
    Supports Singleton and Factory (transient) resolution.
    """

    def __init__(self) -> None:
        self._singletons: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[..., Any]] = {}

    def register_singleton(
        self, interface: type[T], implementation: T | Callable[..., T]
    ) -> None:
        """Register a singleton instance or a factory that returns a singleton."""
        if callable(implementation) and not inspect.isclass(implementation):
            # Factory function — instantiate on first resolve
            self._factories[interface] = implementation
        elif inspect.isclass(implementation):
            # Delay class instantiation to `resolve` so dependencies can be injected
            self._factories[interface] = implementation
        else:
            self._singletons[interface] = implementation

    def register_factory(self, interface: type[T], factory: Callable[..., T]) -> None:
        """Register a factory that is called every time the interface is resolved."""
        self._factories[interface] = factory

    def resolve(self, interface: type[T]) -> T:
        """Resolve an implementation for the given interface."""
        if interface in self._singletons:
            return self._singletons[interface]

        if interface in self._factories:
            factory_or_class = self._factories[interface]

            # Simple auto-wiring attempt for classes
            if inspect.isclass(factory_or_class):
                signature = inspect.signature(factory_or_class.__init__)
                kwargs = {}
                for name, param in signature.parameters.items():
                    if name == "self":
                        continue
                    if param.annotation != inspect.Parameter.empty:
                        # Recursively resolve dependencies if they are registered
                        try:
                            kwargs[name] = self.resolve(param.annotation)
                        except KeyError:
                            if param.default == inspect.Parameter.empty:
                                raise ValueError(
                                    f"Cannot resolve dependency {name}: {param.annotation} for {interface}"
                                )

                instance = factory_or_class(**kwargs)
            else:
                instance = factory_or_class(self)

            self._singletons[interface] = instance
            return instance

        raise KeyError(f"No registration found for {interface.__name__}")
