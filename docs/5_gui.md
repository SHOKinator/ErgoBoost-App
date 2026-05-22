# Архитектура и Документация Проекта ErgoBoost (Часть 5: Графический Интерфейс - GUI)

Presentation Layer написан на `PySide6` (официальный биндинг Qt для Python). Используется кастомный темный дизайн (Dark Mode) посредством Qt StyleSheet (QSS), без применения тяжелых фреймворков или сторонних UI-библиотек.

## 1. Точка Входа и Аутентификация
- `ergoboost_app.py`: Инициализация `QApplication`, загрузка системных путей (sys.path). Запускает цепочку окон.
- `gui/auth_window.py`: Использует `QStackedWidget` для переключения между "Sign In" и "Sign Up". Обращается к `AuthService` для сверки хешей паролей через SQLite. При успешной авторизации запускает `ErgoBoostMainWindow`.

## 2. MainWindow (`gui/main_window.py`)
Окно приложения состоит из:
1. **Header (Верхняя панель)**: Имя пользователя, кнопка DND (Do Not Disturb - таймер игнорирования уведомлений) и Sign Out.
2. **QTabWidget**: Переключатель между вкладками.
3. **QSystemTrayIcon (Системный трей)**: Позволяет свернуть приложение в трей. Содержит меню с действиями (Start, Pause, Quit).
4. **Hotkeys**: Регистрирует глобальные/локальные шорткаты (`QShortcut`) для старта/паузы мониторинга и закрытия оверлея.

## 3. Worker Thread (`gui/monitoring_worker.py`)
GUI не должен зависать при выполнении "тяжелых" задач компьютерного зрения.
- Мониторинг вынесен в класс `MonitoringWorker`, который наследуется от `QObject` и помещается в `QThread`.
- Работает по принципу бесконечного цикла, читая кадры из `cv2.VideoCapture`.
- Инстанцирует все модули-детекторы (`PoseDetector`, `DistanceDetector`, `BlinkDetector`, `ML Predictor`).
- Связь с GUI осуществляется через безопасные для потоков механизмы `Signals` & `Slots`:
  - `frame_ready(np.ndarray)` — отправляет обработанный кадр для отрисовки.
  - `metrics_updated(dict)` — словарь всех показателей для обновления текста в интерфейсе.
  - `alert_triggered` / `overlay_requested` — команды для показа нотификаций.

## 4. Вкладки (Tabs)
1. **DashboardTab (`gui/dashboard_tab.py`)**: 
   - `QLabel` для вывода кадра (отрисовывает `QPixmap` из `np.ndarray`).
   - Панель метрик (Светофорная расцветка: зеленый = OK, красный = BAD).
   - Индикаторы `Presence` (за столом / не за столом), таймеры работы, `Overlay Countdown`.
2. **StatisticsTab (`gui/statistics_tab.py`)**: 
   - Асинхронно через `StatsWorker` загружает графики (Score Trend, Session Duration) и Summary.
   - Вывод `QPixmap` с `matplotlib` и создание PDF отчета.
3. **SessionsTab (`gui/sessions_tab.py`)**: 
   - Вывод таблицы `QTableWidget` со списком прошлых сессий пользователя.
4. **SessionDetailDialog (`gui/session_detail_dialog.py`)**:
   - Открывается по клику "Details" в таблице. Загружает `posture_events`, `eye_events` и рисует детальные графики (Timeline) по каждой метрике для конкретной сессии, плюс экспорт в CSV конкретно этой сессии.
5. **ExercisesTab & SettingsTab**: 
   - Текстовая информация (комплексы разминок).
   - Настройка `Settings` (`QCheckBox`, `QComboBox`, `QSlider`), которые синхронизируются в `settings.yaml` и БД.

## 5. ScreenBlurOverlay (`gui/screen_overlay.py`)
"Радикальный" метод уведомления.
- Если плохая поза сохраняется на протяжении определенного времени (`overlay_delay`, например, 4 секунды), `MonitoringWorker` отправляет сигнал `overlay_countdown`.
- Класс `ScreenBlurOverlay` создает прозрачные окна (`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`), которые располагаются поверх *всех* активных мониторов пользователя. 
- Начинается отсчет (обратный таймер на экране). Если поза не исправлена, экран затемняется полупрозрачным черным фоном (`QPainter.fillRect` с альфа-каналом), блокируя работу, пока человек не выровняет спину или не нажмет Escape. При закрытии приложения используется `atexit`, чтобы оверлеи гарантированно пропали и не заблокировали ОС.
