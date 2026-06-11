# Styles Organization

This folder contains the organized CSS files for the Brookies application, separated by component/feature for better maintainability.

## Structure

- **globals.css** - CSS variables, global resets, and base styles
- **layout.css** - App shell, top bar, navigation, and main layout
- **panel.css** - Panel and card wrapper styles
- **forms.css** - Input, button, label, and form-related styles
- **stock-card.css** - Stock card component and grid styles
- **portfolio.css** - Portfolio, holding forms, industry breakdown, and option chips
- **stock-detail.css** - Stock detail page layout, timeline selector, and detail actions
- **metrics.css** - Radar chart, metric breakdown, and metric explainer styles
- **help.css** - Help page and grade guide styles
- **index.css** - Main import file that consolidates all styles

## Usage

The main entry point is `src/index.css`, which imports `styles/index.css`. All component styles are automatically included through the cascade.

## Colors

Colors are defined as CSS variables in `globals.css`:
- `--color-primary`: #a385f0 (Purple)
- `--color-secondary`: #a9511f (Orange)
- `--color-tertiary`: #4d8371 (Green)
- `--color-highlight`: #e9adc7 (Pink)
- `--color-electric`: #606fe6 (Blue)

## Responsive Design

Breakpoints are at:
- **900px**: Tablets and smaller
- **600px**: Mobile devices

Each CSS file includes responsive styles where applicable.
