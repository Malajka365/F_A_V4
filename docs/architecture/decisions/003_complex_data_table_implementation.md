# Implementation Guide: Match Analysis Template

## Template File (`templates/nezzuk.html`)
```html
{% extends "base.html" %}

{% block content %}
<div class="container mt-4">
  <h3>Match Analysis Dashboard</h3>
  
  <!-- Filter Controls -->
  <div class="row mb-3" id="filters">
    <div class="col">
      <input type="text" class="form-control" placeholder="Filter League" data-column="1">
    </div>
    <div class="col">
      <input type="number" class="form-control" placeholder="Min PR Diff" data-column="5" step="0.1">
    </div>
    <div class="col">
      <input type="number" class="form-control" placeholder="Max Odd" data-column="8" step="0.01">
    </div>
  </div>

  <!-- Data Table -->
  <table class="table table-striped table-hover" id="analysisTable">
    <thead class="thead-dark">
      <tr>
        <th>Date</th>
        <th>League</th>
        <th>Home Team</th>
        <th>Score</th>
        <th>Away Team</th>
        <th>PR Diff</th>
        <th>Home PR</th>
        <th>Away PR</th>
        <th>Home Odd</th>
        <th>Draw Odd</th>
        <th>Away Odd</th>
      </tr>
    </thead>
    <tbody>
      {% for match in matches %}
      <tr>
        <td>{{ match.date }}</td>
        <td>{{ match.league_name }}</td>
        <td>{{ match.home_team }}</td>
        <td>{{ match.goals_home }} - {{ match.goals_away }}</td>
        <td>{{ match.away_team }}</td>
        <td>{{ "%.2f"|format(match.pr_diff) }}</td>
        <td>{{ "%.2f"|format(match.pr_home) }}</td>
        <td>{{ "%.2f"|format(match.pr_away) }}</td>
        <td>{{ "%.2f"|format(match.home_odd) }}</td>
        <td>{{ "%.2f"|format(match.draw_odd) }}</td>
        <td>{{ "%.2f"|format(match.away_odd) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<script>
// Client-side filtering implementation
document.querySelectorAll('#filters input').forEach(input => {
  input.addEventListener('input', () => {
    const column = input.dataset.column;
    const value = input.value.toLowerCase();
    
    Array.from(document.querySelectorAll('#analysisTable tbody tr')).forEach(row => {
      const cell = row.children[column].textContent.toLowerCase();
      row.style.display = (value && !cell.includes(value)) ? 'none' : '';
    });
  });
});
</script>
{% endblock %}
```

## Route Implementation (`app.py`)
```python
@app.route('/analysis')
def analysis():
    with sqlite3.connect('football.db') as conn:
        matches = conn.execute("""
        SELECT f.date, l.name AS league_name, 
               f.home_team, f.goals_home, 
               f.away_team, f.goals_away,
               m.pr_home, m.pr_away, 
               (m.pr_home - m.pr_away) AS pr_diff,
               o.home_odd, o.draw_odd, o.away_odd
        FROM fixtures f
        JOIN leagues l ON f.league_id = l.id
        JOIN match_pr_data m ON f.match_id = m.match_id
        JOIN odds_mapping o ON f.league_id = o.league_id
        """).fetchall()
    return render_template('nezzuk.html', matches=matches)
```

## Navigation Link (`templates/base.html`)
```html
<li class="nav-item">
  <a class="nav-link" href="{{ url_for('analysis') }}">Match Analysis</a>
</li>
```

## Architectural Alignment
- **Component Separation**: Template handles presentation, route handles data fetching
- **Performance**: Client-side filtering reduces server load
- **Consistency**: Follows existing SQLite connection patterns
- **Extensibility**: Filter system designed for additional columns
- **Maintainability**: Centralized data fetching with JOINs
