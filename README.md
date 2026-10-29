# metal slug defense on Windows ported edition

[English](#english) · [Español](#español) · [中文](#中文)

## English

This Windows port is based on the Android version of **Metal Slug Defense 1.46.0**. The game core is statically recompiled for Windows x64, with local adaptations for graphics, audio, input, and saving.

This edition adds keyboard controls and a **16:9 layout**. Expanded backgrounds and adjusted interface positions preserve the original proportions and visible content. Borderless fullscreen is enabled by default.

**Stamina regenerates at 1 point per second.** The original Android version regenerates 1 point per minute.

**Update 26.10.10**

- Added more Metal Slug 7 / XX units and three missions from Metal Slug 7.

Earlier updates are listed in [Update history](#update-history).

### Run

Open the [project page](https://github.com/sprievs7up/metal-slug-defense-on-Windows-ported-edition), click the green **Code** button, and select **Download ZIP**. Extract the entire archive, open the extracted project folder, and run **MSD WINDOWS S1XLV.exe**. Windows 10/11 x64 is required; the runtime is bundled.

The normal, all-units Lv1 and fully unlocked maximum-level EXE launchers share the supplied application icon; LAB is opened from inside the game. Both original 512×512 PNG designs and a 192×192 PNG version are retained under `custom_content/`; the active design is `LOGOAPP2.png`. [Windows icon resources and launchers](docs/WINDOWS_APP_ICON_2026.10.08.md).

The package starts with an initial save. Units can be purchased with medals, and the original daily and event reward paths are preserved. Save files are created in `play_save/`; existing personal progress is excluded from the distributed package. Full campaign coverage and long-term stability remain under evaluation.

To update an existing installation, close the game, back up all existing `play_save*/` folders, extract the new package into a separate folder, and copy those complete save folders into it. The existing save format remains compatible; initial seeds are used only when the corresponding save does not exist.

### Controls

| Key | Action |
| --- | --- |
| `1`–`9`, `0` | Deploy the unit in deck slots 1–10, respectively. The numeric keypad is also supported. |
| `Space` | Activate special attacks for all friendly units whose specials are ready, indicated by the blue glow. |
| <kbd>&#96;</kbd> (backtick) | Upgrade AP production. |
| `-` | Launch the Metal Slug attack when charged. |
| `=` | Attempt to deploy each of the ten deck slots from left to right. Continue through the remaining slots when a unit is unaffordable or on cooldown. |
| `F11` / `Alt+Enter` | Switch between borderless fullscreen and windowed mode. |
| `F9` | Toggle mute. |
| `Esc` | Back; pause or resume a battle. |
| `F12` | Save a screenshot. |
| `Alt+F4` | Close the game. |

Mouse controls remain available. Deployment and special attacks follow the game's AP, cooldown, readiness, unit-limit, and pause conditions.

### Optional all-units Lv1 save

Run **Start_MSD_All_Units_Level1.exe** from the extracted game folder; the corresponding VBS entry remains available. This entry uses the same formal game core and creates an independent save in `play_save_all_units_level1/` on first launch. The normal EXE continues to use `play_save/`; an existing local maximum-level launcher retains its separate save.

The preset owns all 399 original units and 17 community units at **Lv1**; these are the playable community units that existed when the preset was created (up to KT-21). Community units added later, including the PVZ and Metal Slug 6 units, are not part of the preset and are obtained as in a normal save. All nine upgrades under the native army/base customization menu also start at **Lv1**. Maps retain initial progress, no stages are cleared and no prisoners are collected; later stages and worlds require progression. Currency, items and the initial deck follow the formal initial save. World progression and faction-core level limits remain active.

Subsequent launches preserve upgrades, map progress and settings. To use this profile in a new installation, copy its entire `play_save_all_units_level1/` folder. The preset files under `game_data/all_units_level1/` are distributed independently of personal saves.

### Optional fully unlocked maximum-level save

Run **Start_MSD_All_Unlocked_Max_Level.exe**; the corresponding VBS entry remains available. On first launch, this entry creates `play_save_all_unlocked_max_level/` with all **399 original unit records (UnitIDs 1–399) and 17 playable community units at Lv40**, all **nine army/base upgrades at Lv30**, and all six faction cores owned. Maps 1, 2, and 3 have their stages unlocked and cleared, with all **48 area prisoner rewards at 100%**. Historical Event progress follows the initial profile. The 17 community units are those that existed when the preset was created; community units added later, including the PVZ and Metal Slug 6 units, are obtained as in a normal save.

This entry shares the current formal core and preserves its independent progress on subsequent launches. Existing normal and maximum-level saves retain their own directories. To migrate this profile, copy the entire `play_save_all_unlocked_max_level/` folder. Preset files are distributed under `game_data/all_unlocked_max_level/`; implementation and validation scope are recorded in [the profile report](docs/ALL_UNLOCKED_MAX_LEVEL_2026.10.07.md).

### Engineer HP

Engineer units, which advance to build a structure or vehicle on the battlefield, no longer retreat on the first hit. Their HP equals 5% of the HP of the structure they build at the same level, with a minimum of 300 at every level. While HP remains above 0, an engineer keeps advancing or building; when HP is depleted, it retreats as in the original game. The unit STATUS in the upgrade and shop screens shows the HP of the structure; the engineer's own HP follows this rule. The rule is set by `engineer_hp` in `community_content/content.json`, and individual units can use the original retreat on the first hit (`hit_and_run`). Details and per-unit values: [ENGINEER_HP_2026-10-20.md](docs/ENGINEER_HP_2026-10-20.md).

### Online play

Open VERSUS from the main menu and choose LAN (players on the same network) or ONLINE (remote play). Both modes use your current deck and unit levels. For ONLINE, the host creates a room and gives the other player one of the addresses shown together with the room code; the other player enters both. No server is involved, so the host must be reachable from the other player's network: router UPnP (tried automatically), a forwarded UDP port (47631 by default, changeable in the host window; give the other player the WAN IP shown on your router's status page), IPv6, or a virtual LAN tool such as Radmin VPN, Hamachi or ZeroTier. If the host's internet provider uses carrier-grade NAT, swap roles or use one of the other options. On first use, Windows Firewall may ask for permission; allow access on both private and public networks. Both players need the same game version and the same content, including enabled mods; otherwise the match is refused.

### Content authoring

Worlds and stages, community units, custom EVENTs, independent scenes and music are documented in [CONTENT_AUTHORING.md](docs/CONTENT_AUTHORING.md). The bundled catalog registers the Metal Slug 6 missions in Ura World 4 (page 4 of the Ura map). The separate world selection interface remains hidden, and `F6` does not open it.

Mods go in `mods/`, one folder per mod; the format is described in [mods/README.md](mods/README.md). Enable or disable them under MODS in the title-screen OPTION menu; changes take effect after the game restarts. Unit behaviors available to mods are listed in [BEHAVIOR_CATALOG.md](docs/modding/BEHAVIOR_CATALOG.md).

### Update history

**Update 26.10.7**

- Improved the frame rate of the animations of the Metal Slug Advance protagonists WALTER RIAN and TYRA ELSON. In-between frames were added to the walking, normal attack, special attack, melee and death animations of WALTER RIAN and to the walking, normal attack, melee and death animations of TYRA ELSON.

**Update 26.10.6**

- All Metal Slug 6 missions and units have now been added. Come and play!

**Update 26.10.5**

- Added **two missions based on Metal Slug 6**, playable in Ura World 4 (EX MAP 4).
- Added some of the units that appear in Metal Slug 6: IRON CAB and IRON SENTINEL.

**Update 26.10.4**

- Added **three new units from Metal Slug 6**: MV-280C, GIANT HUNTER WALKER and HUNTER.
- Fine-tuned the PVZ EVENT: adjusted the clear times for each rank (S rank within 0:45 in areas 1–2, 1:30 in area 3, 1:55 in area 4 and 2:25 in area 5).

**Update 26.10.3**

- Added the PVZ EVENT and several new units from PVZ. Go play them now!

**Update 26.10.2**

- Redesigned the unit browsing and purchase screens, and added a unit favorites feature (test).
- This UI may still have issues; they will be fixed gradually in later updates.

**Update 26.10.1**

- Added remote online play and LAN online play; feel free to try them out.
- Starting with this version, the version naming scheme changes.

**Update 1.47.3**

- Now you can play all EVENTS just like decade ago
- Historical EVENTs now use the original EventMSD event map, prisoner screen and shops, entered through an EVENT browser page with 13 separate entries (Part 1/Part 2 entries share progress).
- Units sold for medals during each EVENT are available in that EVENT's own shop (bottom SHOP in the instructor base) after the original unlock condition is met; they are no longer mixed into the normal shop.
- The bottom-bar buttons and panels used for EVENTs show the native press highlight, kept until the shutter closes, and the LAB button stays visible while the shutter opens and closes.

**Update 1.47.2**

- Added local two-player versus mode with keyboard/controller support (default controller layout: Xbox 360).

**Update 1.47.1**

- Added AI BOT difficulty levels for use in LAB.

**Update 1.47.0**

- Added an independent fully unlocked maximum-level save profile, including all available units, maximum army and base upgrades, and all POW effects from Maps 1, 2, and 3.
- Added LAB for extensively customizable battles, with available units determined by the player's unlock progress.

LAB documentation: [LAB fixes](docs/LAB_BUGFIX_2026.10.07.md), [LAB menu entry](docs/LAB_MENU_ENTRY_2026.10.07.md), and [LAB and title visuals](docs/LAB_VISUAL_TITLE_2026.10.07.md).

**Update 1.46.4**

- Updated two distinct Mummy variants and the Mummy Summoning Box.

**Update 1.46.3.1**

- Added seven Regular Army infantry units: **Regular Army Shield Soldier**, **Regular Army Rifleman**, **Regular Army Bazooka Soldier**, **Regular Army Gatling Soldier**, **Regular Army Paratrooper**, **Regular Army Rocket Bomb Soldier**, and **Regular Army Mortar Soldier**.
- Corrected parameter selection for retained weapons used by Marco, Fat Marco, Tarma, Fat Tarma, Eri, Christmas Eri, Fio, Fat Fio, and Christmas Fio. Subsequent ranged normal attacks use each character's native special-weapon damage, range, and hit behavior; Fat Eri's existing laser revision passed regression checks.

**Update 1.46.2**

- Added a selector for historical MSD Event missions.
- Enabled acquisition of Event units through the corresponding Event shops and POW rewards.
- Added three units: **DI-COKKA MK.II**, **DI-COKKA MK.III**, and **GIRIDA-O MK.II**.
- Fixed misaligned sprite pixels on **HEAVY B (Future)**.
- Added independent music and sound-effects controls.
- Restored native stationary-laser parameters and bounded damage for Fat Eri's enhanced normal attack, preserving the large-laser visuals.
- Events without a registered shop now hide SHOP in the base and map. Registered Event shops retain their catalog and exchange flow; ordinary unit shops retain native prices.
- Revised status-report file-lock exception handling and the rendering-thread release order on exit.

Level-unlock details: [level unlock verification](docs/UNIT_LEVEL_UNLOCK_2026.10.05.md).

**Update 1.46.1**

- Fixed persistent sprite flickering and body-part misalignment affecting Sol Dae Rokker and its enraged variant.
- Added three independent units: **NOP-03 SARUBIA (Future)**, **M-15A (Future)**, and **HEAVY B (Future)**.

## Español

Esta adaptación para Windows se basa en la versión de Android de **Metal Slug Defense 1.46.0**. El núcleo del juego se recompila estáticamente para Windows x64, con adaptaciones locales de gráficos, audio, controles y guardado.

Esta edición añade controles de teclado y un **formato 16:9**. Los fondos ampliados y la interfaz reubicada conservan las proporciones originales y todo el contenido visible. La pantalla completa sin bordes está activada por defecto.

**La energía (stamina) se recupera a 1 punto por segundo.** La versión original de Android recupera 1 punto por minuto.

**Actualización 26.10.10**

- Se añadieron más unidades de Metal Slug 7 / XX y tres misiones de Metal Slug 7.

Las actualizaciones anteriores se encuentran en [Historial de actualizaciones](#historial-de-actualizaciones).

### Ejecución

Abre la [página del proyecto](https://github.com/sprievs7up/metal-slug-defense-on-Windows-ported-edition), haz clic en el botón verde **Code** y selecciona **Download ZIP**. Extrae el archivo completo, abre la carpeta del proyecto extraída y ejecuta **MSD WINDOWS S1XLV.exe**. Se requiere Windows 10/11 x64; el entorno de ejecución viene incluido.

Los lanzadores EXE normal, de todas las unidades en Lv1 y de todo desbloqueado al nivel máximo comparten el ícono de la aplicación; LAB se abre desde el juego. Los dos diseños PNG originales de 512×512 y una versión PNG de 192×192 se conservan en `custom_content/`; el diseño activo es `LOGOAPP2.png`. [Recursos de íconos y lanzadores de Windows](docs/WINDOWS_APP_ICON_2026.10.08.md).

El paquete comienza con una partida inicial. Las unidades se pueden comprar con medallas, y se conservan las recompensas diarias y de eventos originales. Las partidas se guardan en `play_save/`; el progreso personal existente no se incluye en el paquete distribuido. La cobertura completa de la campaña y la estabilidad a largo plazo siguen en evaluación.

Para actualizar una instalación existente, cierra el juego, haz una copia de seguridad de todas las carpetas `play_save*/`, extrae el nuevo paquete en una carpeta aparte y copia en ella esas carpetas de guardado completas. El formato de guardado sigue siendo compatible; las semillas iniciales solo se usan cuando no existe la partida correspondiente.

### Controles

| Tecla | Acción |
| --- | --- |
| `1`–`9`, `0` | Despliega la unidad de las ranuras 1–10 del mazo, respectivamente. También funciona el teclado numérico. |
| `Espacio` | Activa el ataque especial de todas las unidades aliadas que lo tengan listo (indicado por el brillo azul). |
| <kbd>&#96;</kbd> (acento grave) | Mejora la producción de AP. |
| `-` | Lanza el ataque del Metal Slug cuando está cargado. |
| `=` | Intenta desplegar las diez ranuras del mazo de izquierda a derecha; continúa con las ranuras restantes cuando una unidad no alcanza el AP o está en recarga. |
| `F11` / `Alt+Enter` | Alterna entre pantalla completa sin bordes y modo ventana. |
| `F9` | Activa o desactiva el sonido. |
| `Esc` | Volver; pausa o reanuda una batalla. |
| `F12` | Guarda una captura de pantalla. |
| `Alt+F4` | Cierra el juego. |

El mouse sigue disponible. El despliegue y los ataques especiales respetan las condiciones de AP, recarga, disponibilidad, límite de unidades y pausa del juego.

### Partida opcional con todas las unidades en Lv1

Ejecuta **Start_MSD_All_Units_Level1.exe** desde la carpeta extraída del juego; la entrada VBS correspondiente sigue disponible. Esta entrada usa el mismo núcleo oficial del juego y crea una partida independiente en `play_save_all_units_level1/` en el primer inicio. El EXE normal sigue usando `play_save/`; un lanzador local de nivel máximo ya existente conserva su partida aparte.

El perfil incluye las 399 unidades originales y 17 unidades comunitarias, todas en **Lv1**; son las unidades comunitarias jugables que existían cuando se creó el perfil (hasta KT-21). Las unidades comunitarias añadidas después, como las de PVZ y de Metal Slug 6, no forman parte del perfil y se obtienen como en una partida normal. Las nueve mejoras del menú nativo de personalización de ejército/base también empiezan en **Lv1**. Los mapas conservan el progreso inicial: no hay etapas superadas ni prisioneros rescatados, y las etapas y mundos posteriores se desbloquean al avanzar. Las monedas, los objetos y el mazo inicial siguen la partida inicial oficial. Los límites de nivel por progreso de mundos y por núcleos de facción siguen activos.

Los inicios posteriores conservan las mejoras, el progreso del mapa y la configuración. Para usar este perfil en una instalación nueva, copia toda su carpeta `play_save_all_units_level1/`. Los archivos del perfil en `game_data/all_units_level1/` se distribuyen por separado de las partidas personales.

### Partida opcional con todo desbloqueado al nivel máximo

Ejecuta **Start_MSD_All_Unlocked_Max_Level.exe**; la entrada VBS correspondiente sigue disponible. En el primer inicio, esta entrada crea `play_save_all_unlocked_max_level/` con los **399 registros de unidades originales (UnitID 1–399) y 17 unidades comunitarias jugables en Lv40**, las **nueve mejoras de ejército/base en Lv30** y los seis núcleos de facción. Los mapas 1, 2 y 3 tienen sus etapas desbloqueadas y superadas, con las **48 recompensas de prisioneros por área al 100 %**. El progreso de los Event históricos sigue el perfil inicial. Las 17 unidades comunitarias son las que existían cuando se creó el perfil; las añadidas después, como las de PVZ y de Metal Slug 6, se obtienen como en una partida normal.

Esta entrada comparte el núcleo oficial actual y conserva su progreso independiente en los inicios posteriores. Las partidas normales y de nivel máximo existentes conservan sus propias carpetas. Para migrar este perfil, copia toda la carpeta `play_save_all_unlocked_max_level/`. Los archivos del perfil se distribuyen en `game_data/all_unlocked_max_level/`; la implementación y el alcance de la validación se describen en [el informe del perfil](docs/ALL_UNLOCKED_MAX_LEVEL_2026.10.07.md).

### Vida de los ingenieros

Las unidades de ingeniería, que avanzan para construir una estructura o un vehículo en el campo de batalla, ya no se retiran con el primer impacto. Su vida equivale al 5 % de la vida de la estructura que construyen al mismo nivel, con un mínimo de 300 en todos los niveles. Mientras su vida sea mayor que 0, siguen avanzando o construyendo; al agotarse, se retiran como en el juego original. El STATUS de las pantallas de mejora y tienda muestra la vida de la estructura; la vida del ingeniero sigue esta regla. La regla se define en `engineer_hp` de `community_content/content.json`, y unidades concretas pueden usar la retirada original al primer impacto (`hit_and_run`). Detalles y valores por unidad: [ENGINEER_HP_2026-10-20.md](docs/ENGINEER_HP_2026-10-20.md).

### Juego en línea

Abre VERSUS desde el menú principal y elige LAN (jugadores en la misma red) u ONLINE (juego remoto). Ambos modos usan tu mazo actual y los niveles de tus unidades. En ONLINE, el anfitrión crea una sala y le pasa al otro jugador una de las direcciones que aparecen junto con el código de la sala; el otro jugador escribe ambos datos. No se usa ningún servidor, así que el anfitrión debe ser accesible desde la red del otro jugador: UPnP del router (se intenta automáticamente), un puerto UDP redirigido (47631 por defecto, se puede cambiar en la ventana del anfitrión; pásale al otro jugador la IP WAN que muestra la página de estado del router), IPv6 o una herramienta de red local virtual como Radmin VPN, Hamachi o ZeroTier. Si el proveedor de internet del anfitrión usa CGNAT, intercambien los papeles o usen otra de estas opciones. La primera vez, el Firewall de Windows puede pedir permiso; permite el acceso en redes privadas y públicas. Ambos jugadores necesitan la misma versión del juego y el mismo contenido, incluidos los mods activados; de lo contrario, la partida se rechaza.

### Creación de contenido

Los mundos y etapas, las unidades comunitarias, los EVENT propios, y los escenarios y la música independientes se documentan en [CONTENT_AUTHORING.md](docs/CONTENT_AUTHORING.md). El catálogo incluido registra las misiones de Metal Slug 6 en el Mundo Ura 4 (página 4 del mapa Ura). La interfaz independiente de selección de mundos sigue oculta y `F6` no la abre.

Los mods se colocan en `mods/`, una carpeta por mod; el formato se describe en [mods/README.md](mods/README.md). Actívalos o desactívalos en MODS, dentro del menú OPTION de la pantalla de título; los cambios se aplican al reiniciar el juego. Los comportamientos de unidad disponibles para los mods se enumeran en [BEHAVIOR_CATALOG.md](docs/modding/BEHAVIOR_CATALOG.md).

### Historial de actualizaciones

**Actualización 26.10.7**

- Se mejoró la frecuencia de fotogramas de las animaciones de los protagonistas de Metal Slug Advance, WALTER RIAN y TYRA ELSON. Se añadieron fotogramas intermedios a las animaciones de avance, ataque normal, ataque especial, cuerpo a cuerpo y muerte de WALTER RIAN, y a las de avance, ataque normal, cuerpo a cuerpo y muerte de TYRA ELSON.

**Actualización 26.10.6**

- Ya están disponibles todas las misiones y unidades de Metal Slug 6. ¡Ven a jugarlas!

**Actualización 26.10.5**

- Se añadieron **dos misiones basadas en Metal Slug 6**, que puedes jugar en el Mundo Ura 4 (EX MAP 4).
- Se añadieron algunas de las unidades que aparecen en Metal Slug 6: IRON CAB e IRON SENTINEL.

**Actualización 26.10.4**

- Se añadieron **tres unidades nuevas de Metal Slug 6**: MV-280C, CAZADOR CAMINANTE GIGANTE (GIANT HUNTER WALKER) y CAZADOR (HUNTER).
- Se ajustó el PVZ EVENT: se cambiaron los tiempos necesarios para cada rango (rango S en 0:45 en las zonas 1 y 2, 1:30 en la zona 3, 1:55 en la zona 4 y 2:25 en la zona 5).

**Actualización 26.10.3**

- Se añadieron el PVZ EVENT y varias unidades nuevas de PVZ. ¡Ve a jugarlos!

**Actualización 26.10.2**

- Se rediseñaron las pantallas de exploración y compra de unidades, y se añadió una función de unidades favoritas (en prueba).
- Esta interfaz aún puede tener problemas; se irán corrigiendo en próximas actualizaciones.

**Actualización 26.10.1**

- Se añadió el juego en línea remoto y por red local (LAN); puedes probarlo por tu cuenta.
- A partir de esta versión cambia el formato de los números de versión.

**Actualización 1.47.3**

- Ahora puedes jugar todos los EVENT como hace una década.
- Los EVENT históricos ahora usan el mapa de eventos EventMSD, la pantalla de prisioneros y las tiendas originales, y se accede a ellos desde una página de exploración de EVENT con 13 entradas independientes (las entradas Parte 1 y Parte 2 comparten el progreso).
- Las unidades que se vendían por medallas durante cada EVENT ahora están en la tienda propia de ese EVENT (SHOP de la barra inferior en la base de la instructora) una vez cumplida la condición de desbloqueo original; ya no se mezclan con la tienda normal.
- Los botones y paneles de la barra inferior de los EVENT muestran el resaltado nativo al pulsarlos hasta que se cierra la compuerta, y el botón LAB permanece visible mientras la compuerta se abre y se cierra.

**Actualización 1.47.2**

- Se añadió el modo versus local para dos jugadores, con teclado o control (distribución predeterminada del control: Xbox 360).

**Actualización 1.47.1**

- Se añadieron niveles de dificultad de BOT de IA para usar en LAB.

**Actualización 1.47.0**

- Se añadió un perfil de guardado independiente con todo desbloqueado y al nivel máximo, que incluye todas las unidades disponibles, las mejoras de ejército y de base al máximo, y todos los efectos POW de los mapas 1, 2 y 3.
- Se añadió LAB, para batallas ampliamente personalizables; las unidades disponibles dependen del progreso de desbloqueo del jugador.

Documentación de LAB: [correcciones de LAB](docs/LAB_BUGFIX_2026.10.07.md), [acceso a LAB desde el menú](docs/LAB_MENU_ENTRY_2026.10.07.md) y [elementos visuales de LAB y del título](docs/LAB_VISUAL_TITLE_2026.10.07.md).

**Actualización 1.46.4**

- Se actualizaron dos variantes distintas de Momia y el Generador de Momias.

**Actualización 1.46.3.1**

- Se añadieron siete unidades de infantería del Ejército Regular: **Soldado blindado**, **Fusilero**, **Soldado bazuca**, **Cañonero**, **Paracaidista**, **Soldado con misil** y **Mortero** (en el juego aparecen con el prefijo «EJÉRCITO REGULAR»).
- Se corrigió la selección de parámetros de las armas que conservan Marco, Marco gordo, Tarma, Tarma gordo, Eri, Eri Navidad, Fio, Fio gorda y Fio Navidad. Los ataques normales a distancia posteriores usan el daño, el alcance y el comportamiento de impacto del arma especial nativa de cada personaje; la corrección anterior del láser de Eri gorda superó las pruebas de regresión.

**Actualización 1.46.2**

- Se añadió un selector de misiones de los Event históricos de MSD.
- Se habilitó la obtención de unidades de Event mediante las tiendas de cada Event y las recompensas POW.
- Se añadieron tres unidades: **DI-COKKA MK.II**, **DI-COKKA MK.III** y **GIRIDA-O MK.II**.
- Se corrigieron píxeles desalineados del sprite de **HEAVY B (Futuro)**.
- Se añadieron controles independientes de música y de efectos de sonido.
- Se restauraron los parámetros nativos del láser fijo y el daño limitado del ataque normal mejorado de Eri gorda, conservando la apariencia del láser grande.
- Los Event sin tienda registrada ahora ocultan SHOP en la base y en el mapa. Las tiendas de Event registradas conservan su catálogo y su flujo de canje; las tiendas normales de unidades conservan los precios nativos.
- Se revisó el manejo de excepciones por bloqueo de archivos del informe de estado y el orden de liberación del hilo de renderizado al salir.

Detalles del desbloqueo de niveles: [verificación del desbloqueo de niveles](docs/UNIT_LEVEL_UNLOCK_2026.10.05.md).

**Actualización 1.46.1**

- Se corrigieron el parpadeo persistente del sprite y el desalineamiento de partes del cuerpo de Sol Dae Rokker y su variante enfurecida.
- Se añadieron tres unidades independientes: **NOP-03 SARUBIA (Futuro)**, **M-15A (Futuro)** y **HEAVY B (Futuro)**.

## 中文

本项目基于安卓原版 **《合金弹头塔防》（Metal Slug Defense）1.46.0**，将游戏移植至 Windows。游戏核心通过静态重编译生成 Windows x64 代码，并适配本地的图形、音频、输入与存档功能。

本版本新增键盘操控系统，并将画面调整为 **16:9 布局**。通过扩展背景与调整界面位置，保持角色及素材的原有比例，并保留原画面的可见内容。默认采用无边框全屏模式。

**体力每秒恢复 1 点。** 安卓原版的恢复速率为每分钟 1 点。

**26.10.10 更新**

- 新增额外的《合金弹头7》/《合金弹头XX》单位，以及 3 个来自《合金弹头7》的关卡

此前的更新见[更新记录](#更新记录)。

### 运行方法

在[项目主页](https://github.com/sprievs7up/metal-slug-defense-on-Windows-ported-edition)点击绿色 **Code** 按钮，选择 **Download ZIP** 下载压缩包。完整解压后，打开解压得到的项目文件夹，启动 **MSD WINDOWS S1XLV.exe**。适用于 Windows 10/11 x64，运行依赖已随包提供。

普通、全兵种 Lv1 及全解锁满级的 EXE 入口统一使用用户提供的应用图标；LAB 在游戏内进入。两份 512×512 PNG 原稿与 192×192 PNG 版本保留在 `custom_content/`，当前采用 `LOGOAPP2.png`。实施与资源规格见 [Windows 应用图标与入口说明](docs/WINDOWS_APP_ICON_2026.10.08.md)。

分发包采用初始存档，玩家可以使用勋章购买单位；原版每日奖励、活动奖励及对应解锁流程均保留。个人进度保存在 `play_save/`，分发包不包含已有个人进度。全关卡覆盖与长期运行稳定性仍需持续验证。

更新已有安装时，请先关闭游戏并备份所有已有的 `play_save*/` 存档目录，将新运行包解压至独立目录，再将这些完整存档目录复制至该目录。现有存档格式保持兼容；初始种子仅在对应存档不存在时使用。

### 按键操作

| 按键 | 功能 |
| --- | --- |
| `1`–`9`、`0` | 分别出击编队第 1–10 个槽位的单位；支持数字小键盘。 |
| `空格` | 使所有绝招已就绪的友方单位发动绝招，就绪状态以蓝光表示。 |
| <kbd>&#96;</kbd>（反引号） | 升级 AP 生产。 |
| `-` | 在充能完成后发动弹头车攻击。 |
| `=` | 从左至右依次尝试出击全部十个槽位；遇到 AP 不足或冷却中的单位时，继续尝试后续槽位。 |
| `F11` / `Alt+Enter` | 切换无边框全屏与窗口模式。 |
| `F9` | 切换静音状态。 |
| `Esc` | 返回；在战斗中暂停或恢复。 |
| `F12` | 保存截图。 |
| `Alt+F4` | 关闭游戏。 |

保留鼠标操作。出击与绝招均遵守游戏的 AP、冷却、就绪状态、单位数量上限及暂停条件。

### 全兵种 Lv1 可替代存档

在解压后的游戏目录中启动 **Start_MSD_All_Units_Level1.exe**，对应 VBS 入口继续可用。该入口使用同一正式版核心，首次启动时在 `play_save_all_units_level1/` 创建独立存档。普通 EXE 继续使用 `play_save/`；本地既有满级入口继续使用其独立存档。

该预设包含全部 **399 个原版兵种及 17 个社区兵种**，均已拥有且初始为 **Lv1**；这 17 个为制作预设时已有的可用社区兵种（至 KT-21）。之后新增的社区兵种（PVZ 与《合金弹头6》的单位等）不在预设内，按普通存档的方式获得。“我方阵营”的 **9 项强化均为 Lv1**。地图采用初始进度，关卡均未通关、捕虏均未收集，后续关卡及世界按游戏规则逐步解锁。货币、道具及初始编队沿用正式版初始存档。世界进度与军队核等级上限继续生效。

再次启动时保留已经完成的升级、地图进度及设置。迁移至新安装目录时，复制完整的 `play_save_all_units_level1/`。预设文件位于 `game_data/all_units_level1/`，发行文件与个人进度分别保存。

### 全解锁满级独立存档

启动 **Start_MSD_All_Unlocked_Max_Level.exe**，对应 VBS 入口继续可用。首次启动时在 `play_save_all_unlocked_max_level/` 创建独立存档，包含全部 **399 个原版单位记录（UnitID 1–399）和 17 款可选社区单位，均为 Lv40**；“我方阵营”的 **九项基地强化均为 Lv30**，六阵营核心全部持有。地图 1、2、3 的关卡开放并完成通关，**48 项区域人质奖励效果均为 100%**。历史活动进度沿用初始预设。17 款社区单位为制作预设时已有的单位；之后新增的社区单位（PVZ 与《合金弹头6》的单位等）按普通存档的方式获得。

该入口共用当前正式版核心，后续启动保留该独立存档的游戏进度。既有普通入口和原满级入口继续使用各自存档目录。迁移时复制完整的 `play_save_all_unlocked_max_level/`；预设位于 `game_data/all_unlocked_max_level/`，实施与核验范围见 [独立预设说明](docs/ALL_UNLOCKED_MAX_LEVEL_2026.10.07.md)。

### 工兵生命

修筑类单位（前进至战场修筑建筑或载具的工兵）受击后不再立即撤退。其生命为修筑对象同等级生命的 5%，各等级下限为 300。生命大于 0 时继续前进或修筑，耗尽时按原版撤退。单位强化与商店界面的 STATUS 显示修筑对象的生命，工兵自身生命按本规则计算。规则由 `community_content/content.json` 的 `engineer_hp` 设定，个别单位可设为原版的受击即撤退（`hit_and_run`）。说明与各单位数值见 [ENGINEER_HP_2026-10-20.md](docs/ENGINEER_HP_2026-10-20.md)。

### 联机对战

在主菜单打开「對戰」，选择 LAN（同一网络的玩家）或 ONLINE（远程联机）。两种模式都使用当前编队与单位等级。远程联机时，房主建立房间后，把窗口中显示的其中一个地址与房间码告诉对方，对方输入这两项即可连接。联机不经过服务器，房主必须能被对方的网络直接访问：路由器 UPnP（游戏会自动尝试）、转发 UDP 端口（默认 47631，可在房主窗口中更改；把路由器状态页显示的 WAN（外网）IP 告诉对方）、IPv6，或 Radmin VPN、Hamachi、ZeroTier 等虚拟局域网工具。房主的网络若为运营商级 NAT，可以交换房主，或使用上述其他方式。首次使用时 Windows 防火墙可能询问是否允许网络访问，请同时勾选“专用网络”和“公用网络”。双方须使用相同的游戏版本与相同的内容（含已启用的模组），否则无法匹配。

### 内容制作

世界与关卡、社区单位、自制 EVENT、独立场景和音乐的配置方法见 [CONTENT_AUTHORING.md](docs/CONTENT_AUTHORING.md)。随包目录登记了《合金弹头6》的各个任务，位于里世界 4（里地图第 4 页）。独立的世界选择界面仍暂时隐藏，`F6` 暂不打开该界面。

模组放在 `mods/` 下，每个模组一个文件夹，格式见 [mods/README.md](mods/README.md)。在标题画面 OPTION 的「MOD 設定」中启用或停用，重启游戏后生效。模组可调用的单位行为见 [BEHAVIOR_CATALOG.md](docs/modding/BEHAVIOR_CATALOG.md)。

### 更新记录

**26.10.7 更新**

- 优化了《合金弹头 Advance》中主角（WALTER RIAN、TYRA ELSON）的帧率动画：WALTER RIAN 的前进、普通攻击、绝招、近战与死亡动作，TYRA ELSON 的前进、普通攻击、近战与死亡动作增加了中间帧

**26.10.6 更新**

- 现在《合金弹头6》的全部关卡和单位已经更新完毕，快来进行游玩吧

**26.10.5 更新**

- 新增**两个取材自《合金弹头6》的任务**，可在里世界 4 游玩
- 新增部分在《合金弹头6》中登场的单位：铁甲车头（IRON CAB）、钢铁哨兵（IRON SENTINEL）

**26.10.4 更新**

- 新增**三个来自《合金弹头6》的单位**：MV-280C、巨型HUNTER WALKER、猎人（HUNTER）
- 对 PVZ EVENT 进行了微调：调整了各评价所需的通关时间（S 评价：第一、二大关 45 秒内，第三大关 1:30 内，第四大关 1:55 内，第五大关 2:25 内）

**26.10.3 更新**

- 现已经加入PVZ EVENT以及一些来自PVZ的新unit，快去游玩吧

**26.10.2 更新**

- 重制了单位的浏览与购买UI界面，以及额外的单位收藏功能（测试）
- 此UI可能还存在问题，后续会逐渐修复

**26.10.1 更新**

- 新加入了远程联机与局域网联机功能，玩家可以自己进行尝试
- 现在开始版本号名称方式会发生改变

**1.47.3 更新**

- 你现在可以游玩所有的EVENT了
- 历史 EVENT 改用原版活动地图、人质页面与商店，并由 EVENT 浏览页进入，共 13 个独立入口（第一部分与第二部分共享进度）。
- 各 EVENT 期间以勋章出售的单位，改在该 EVENT 的独立商店（女教官基地底栏 SHOP）中购买，满足原版开售条件后开放，不再与普通商店混在一起。
- EVENT 相关的底栏按钮与面板显示原生按压反馈，并保持至闸门合拢；LAB 按钮在开闸与关闸过程中保持显示。

**1.47.2 更新**

- 新添加本地双人对战功能，可使用键盘/手柄进行对战（手柄操作默认XBOX360操作模式）

**1.47.1 更新**

- 加入了不同等级的AI BOT以在LAB中使用

**1.47.0 更新**

- 新增全解锁满级独立存档入口，涵盖全部可用单位、满级我方阵营与基地强化，以及地图 1、2、3 的全部人质效果。
- 增加LAB 实验室功能，玩家现可以直接高度自定义对战内容（取决于你解锁的单位）

LAB 功能说明：[LAB 修复记录](docs/LAB_BUGFIX_2026.10.07.md)、[LAB 菜单入口说明](docs/LAB_MENU_ENTRY_2026.10.07.md)、[LAB 与标题视觉修订](docs/LAB_VISUAL_TITLE_2026.10.07.md)。

**1.46.4 更新**

- 更新两种不同的木乃伊以及木乃伊召唤箱

**1.46.3.1 更新**

- 新增七种正规军小兵：**正规军盾牌兵**、**正规军步枪兵**、**正规军反坦克兵**、**正规军加特林机枪兵**、**正规军伞兵**、**正规军冲天火箭弹兵**及**正规军迫击炮兵**。
- 修复马可、胖马可、塔玛、胖塔玛、英里、圣诞英里、菲欧、胖菲欧及圣诞菲欧保留武器时的参数选择错误。后续远程普攻沿用各自原生特殊武器的伤害、范围及命中行为；胖英里的既有激光修订通过回归检查。

**1.46.2 更新**

- 新增 MSD 历史 Event 任务选择功能。
- 支持通过对应 Event 商店及捕虏奖励获取活动单位。
- 新增三个单位：**基 · 寇卡坦克 MK.II**、**基 · 寇卡坦克 MK.III**、**吉利塔 · O MK.II**。
- 修复**未来重装 B 型**的像素错位问题。
- 新增音乐、音效独立开关。
- 修复胖子英里强化普攻的大激光参数，恢复原生静止激光与受限伤害行为，保留大激光显示。
- 未登记商店的 Event 隐藏基地与地图 SHOP；已登记商店保留目录与兑换流程，普通单位商店保留原生价格。
- 修订状态报告文件锁异常处理及退出时的渲染线程释放顺序。

等级解锁规则见 [等级解锁修复记录](docs/UNIT_LEVEL_UNLOCK_2026.10.05.md)。

**1.46.1 更新**

- 修复索尔罗卡（Sol Dae Rokker）及其愤怒版持续出现的贴图闪烁与身体部件错位问题。
- 新增三个独立单位：**爆竹红（未来）**、**M-15A 型（未来）**、**未来重装 B 型**。
