# Decision: Complex Data Table Implementation

## Context
Need to display aggregated match/odds/PR data from multiple tables with filtering capabilities.

## Decision
Implement a server-rendered table using:
1. **Flask/Jinja template inheritance** from base layout
2. **Bootstrap Table** for responsive presentation
3. **Client-side filtering** with DOM manipulation
4. **Composite SQL view** joining:
   - Fixtures
   - Match PR data 
   - Odds mapping
   - Helper tables

## Consequences
- Allows reuse of existing DB connections
- Maintains consistent styling with other templates
- Filtering happens client-side for performance
- Requires view synchronization logic
