# Design Tokens — Rehavid (Manual de Identidad, v8)

Fuente: bloque `:root` y CSS del layout en `frontend/rehavid_v13_produccion.html` (líneas ~12–600).

Principio de la paleta: **solo morado `#4025CE`, verde `#02E577` y blanco. Sin negros ni grises decorativos** — todos los tonos de texto y línea son tintados con morado.

## Tipografía

- Familia principal: **Outfit** (Google Fonts, pesos 300, 400, 500, 600, 700, 800):
  `https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap`
- Stack body: `font-family: Outfit, Arial, -apple-system, sans-serif;` · tamaño base `13.5px` · `line-height: 1.5` · antialiased.
- Clase `.serif`: `Outfit, Arial, Georgia, serif` (no hay serif real, todo es Outfit).
- Clase `.mono`: `'Outfit Mono', 'Courier New', monospace` (usada para seriales/códigos). Nota: "Outfit Mono" no se carga de Google Fonts — en la práctica cae a Courier New.

## Variables CSS de `:root`

### Superficies (papeles)
| Token | Valor | Uso |
|---|---|---|
| `--paper` | `#FFFFFF` | blanco puro · base |
| `--paper-2` | `#FBFAFE` | blanco con tinte morado · cards secundarias |
| `--paper-3` | `#F4F0FB` | lavanda papel · fondos sutiles |

### Texto (tintado en morado, no grises)
| Token | Valor | Uso |
|---|---|---|
| `--ink` | `#1F1042` | morado muy oscuro · texto principal |
| `--ink-2` | `#3A2880` | morado oscuro · texto secundario |
| `--ink-3` | `#5A4A95` | morado medio · texto terciario |
| `--ink-4` | `#8478B2` | lavanda profundo · subtext |
| `--ink-5` | `#A89ECD` | lavanda claro · hints |
| `--ink-6` | `#C5BFDE` | muy claro · placeholders |

### Líneas
| Token | Valor |
|---|---|
| `--line` | `#E5DFF6` (línea estándar) |
| `--line-2` | `#D5CCEC` (línea visible) |
| `--line-3` | `#F0EBFA` (línea muy sutil) |

### Marca
| Token | Valor | Uso |
|---|---|---|
| `--brand` | `#4025CE` | **morado oficial** |
| `--brand-dark` | `#2A1788` | morado profundo (fondo del sidebar y panel izquierdo del login) |
| `--brand-light` | `#6952DA` | morado claro |
| `--brand-soft` | `#EBE7FB` | lavanda muy claro · backgrounds |
| `--brand-line` | `rgba(64,37,206,0.18)` | |
| `--accent-green` | `#02E577` | **verde oficial** |
| `--green-dark` | `#00A055` | verde oscuro |
| `--green-light` | `#6FF0AC` | verde claro |
| `--accent-green-soft` | `#DCF9E9` | verde muy claro · backgrounds |

### Alias (heredados de versiones grises, ahora apuntan a marca)
| Token | Valor | Nota |
|---|---|---|
| `--accent` | `#4025CE` | antes `#1A1A1A` |
| `--accent-2` | `#2A1788` | antes `#2C3E50` |
| `--accent-soft` | `#EBE7FB` | antes `#F2F2F2` |

### Semáforo (estados)
| Token | Valor | Fondo asociado |
|---|---|---|
| `--good` | `#00A055` | `--good-bg: #DCF9E9` |
| `--warn` | `#B8770F` | `--warn-bg: #FBF3E0` |
| `--bad` | `#B23B5C` (magenta tirando a morado) | `--bad-bg: #FAE7EC` |
| `--info` | `#4025CE` | `--info-bg: #EBE7FB` |

### Sombras, layout y radios
| Token | Valor |
|---|---|
| `--sh-1` | `0 1px 0 rgba(64,37,206,.04)` |
| `--sh-2` | `0 1px 0 rgba(64,37,206,.05)` |
| `--sh-3` | `0 4px 16px rgba(64,37,206,.08)` |
| `--side` | `232px` (ancho del sidebar) |
| `--radius` / `--radius-2` | `2px` / `2px` (esquinas casi rectas, look editorial) |

Las sombras siempre llevan tinte morado `rgba(64,37,206,…)`, nunca negro.

## Sidebar (`aside.sidebar`)

- Fondo sólido `var(--brand-dark)` (#2A1788), texto `var(--paper)` blanco, ancho `var(--side)` = 232px, `position: fixed; top: 28px` (debajo del banner demo de 28px), altura `calc(100vh - 28px)`.
- Glyph de marca: cuadrado 30×30 con fondo `var(--accent)` (#4025CE), letra blanca Outfit 500.
- Divisores de menú: texto 9.5px uppercase `rgba(255,255,255,0.35)`, `letter-spacing: 0.12em`, `border-top: 1px solid rgba(255,255,255,0.06)`.
- Botones de menú: 12.5px, color `rgba(255,255,255,0.7)`; hover → blanco con `background: rgba(255,255,255,0.04)`; activo → `rgba(255,255,255,0.06)` + barra indicadora izquierda de 2px en `var(--brand)`.
- Footer: `border-top: 1px solid rgba(255,255,255,0.07)`; avatar circular 30px fondo `var(--accent)`.
- Panel izquierdo del login (mismo lenguaje): fondo `var(--brand-dark)` con decoración `radial-gradient(circle, rgba(44,62,80,0.18), transparent 70%)` en círculo de 400px abajo/derecha.

## Tarjetas KPI (`.kpi-grid` / `.kpi`)

- Grid: `repeat(4, 1fr)`, `gap: 12px` (2 columnas bajo el breakpoint responsive).
- Tarjeta: fondo blanco, `border: 1px solid var(--line)`, padding `16px 18px`, **sin sombra ni radio** (estilo plano/editorial).
- `.tag` (etiqueta): 10.5px uppercase, `letter-spacing: 0.05em`, color `var(--ink-4)`.
- `.value` (cifra): Outfit 26px peso 400, color `var(--ink)`, `letter-spacing: -0.01em`; unidad 14px en `var(--ink-3)`.
- `.sub`: 11px en `var(--ink-3)`.
- `.delta` (variación): píldora 10.5px — positiva `background: var(--accent-green-soft); color: #008C50` · negativa `var(--bad-bg)`/`var(--bad)` · neutra `var(--paper-2)`/`var(--ink-3)`.
- Variantes con borde izquierdo de 3px: `.kpi.alert` → `var(--bad)`, `.kpi.warn` → `var(--warn)`, `.kpi.good` → `var(--good)`, `.kpi.accent` → `var(--accent)`.

## Gradientes distintivos recurrentes

- Paneles destacados: `linear-gradient(135deg, #F0EBFD 0%, #FAFAFB 100%)` (y su inverso `#FAFAFB → #F0EBFD`) con `border: 1.5px solid var(--brand-light)` y `border-radius: 12px`.
- Variante con acento superior: mismo gradiente + `border-top: 4px solid var(--brand)` y borde punteado (`1.5px dashed var(--brand-light)`).
- Aviso ámbar: `linear-gradient(90deg, #FFF3CD 0%, #FFE69C 100%)` con `border: 2px solid #B58900`.
- Transición sutil de fondo: `linear-gradient(180deg, white 0%, var(--paper) 100%)`.

## Otros colores puntuales fuera de `:root`

- Estados de equipo (chips): en preparación `#B58900` / bg `#FFF8E1`; en revisión `#8B5CF6` / bg `#F3E8FF`; en mantenimiento bg `#FFE9E9`; en uso bg `#EFEAFC`; en tránsito bg `#F0EBFD`; disponible bg `#E6FFF1`.
- Escala de intensidad del mini-calendario: `#FAFAFA` → `#EBE7FB` → `#C9BEF1` → `#9786E0`.
- Verde "en curso" para pills de solicitudes: `#008C50`.
- Banner demo: fondo `var(--ink)` (#1F1042), texto blanco, 11px, sticky top, z-index 200.
