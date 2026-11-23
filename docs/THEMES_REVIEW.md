# Огляд 29 тем

Метод: для кожної теми порахований контраст (WCAG) тексту, приглушеного тексту, тексту на акценті
та акценту на панелі; для кожної пари тем відстань кольорів BG + PANEL + ACCENT (RGB).

## Контраст
Усі 29 тем проходять AA: основний текст 11.4-19.5 : 1, приглушений не нижче 4.5 : 1 (найнижчі ARCTIC і MONO),
текст на акценті 4.5-15.2 : 1. Проблемних тем немає.

## Майже дублікати (сума відстаней < 60)
GRAPHITE ~ DARK ~ ELECTRIC ~ MINIMAL_DARK · SLATE ~ MIDNIGHT ~ COBALT · TRUE_BLACK ~ NEXUS ·
TITANIUM ~ NEON_PULSE (відстань 19) · BURGUNDY ~ PERFORMANCE_RED · ESPRESSO ~ COPPER ~ INDUSTRIAL ·
DEEP_TEAL ~ CYBER · ARCTIC ~ LIGHT.

## Пропозиція: 18 тем
| Група | Залишити | Приєднати (alias) |
|---|---|---|
| Темні нейтральні | TITANIUM (за замовчуванням), GRAPHITE, AMOLED, TRUE_BLACK | NEON_PULSE → TITANIUM; DARK, ELECTRIC, MINIMAL_DARK → GRAPHITE; NEXUS → TRUE_BLACK |
| Сині та фіолетові | MIDNIGHT, PURPLE, AUBERGINE | SLATE, COBALT → MIDNIGHT |
| Зелені та бірюзові | CYBER, GREEN, FOREST, TACTICAL | DEEP_TEAL → CYBER |
| Теплі | BURGUNDY, ESPRESSO, INDUSTRIAL | PERFORMANCE_RED → BURGUNDY; COPPER → ESPRESSO |
| Світлі | ARCTIC, IVORY, SAGE, MONO | LIGHT → ARCTIC |

Застосування: прибрати 11 палітр з `PALETTES`, додати їх у `THEME_ALIASES` (збережені налаштування
користувачів перейдуть на найближчу тему), оновити лічильник тем у README та тестах.
Залишено без змін: це рішення про продукт, його ухвалює власник.

**Рішення власника (2026-11-24): застосовано консолідацію до 18 тем.**
11 майже дублів прибрано з `PALETTES` і додано до `THEME_ALIASES`, тому збережені
налаштування зі старими назвами автоматично відкриваються найближчою темою.
