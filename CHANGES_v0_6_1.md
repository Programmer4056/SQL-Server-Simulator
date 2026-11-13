# v0.6.1 - Diagram interaction and welcome layout fix

- Fixed the root cause of failed two-click field links: the preview QGraphicsPathItem was above the destination table and captured the hit test. It now renders beneath cards; node hit-testing iterates the stacked graphics items and ignores the preview.
- Removed automatic shrink-to-fit after every rebuild, which made fields too small to interact with. Added explicit **Fit Diagram** and **100%** controls.
- Added live two-step guidance for selecting source/target fields. Supports both directions of PK/FK selection through the existing normalized mapping wizard.
- Rebuilt the welcome panel with a scroll-safe 540 px minimum card height, 135 px title, 115 px description, an explicit line break in the English title, and reduced typography to prevent clipped final lines. On smaller windows the welcome area scrolls rather than cutting text.
- No modifications to core foreign-key validation, deletion, identity, or SQL data handling.
- The 0.6.1 builder runs all prior and new regression tests on Windows before packaging.
