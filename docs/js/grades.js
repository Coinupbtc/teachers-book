/**
 * GradeComputer — port of backend GradeComputer weighted averages + letter grades.
 * Category.weight is a fraction (e.g. 0.35 = 35%). weight_pct is derived for the UI.
 */
(function (global) {
  "use strict";

  function toLetter(pct) {
    if (pct >= 93) return "A";
    if (pct >= 90) return "A-";
    if (pct >= 87) return "B+";
    if (pct >= 83) return "B";
    if (pct >= 80) return "B-";
    if (pct >= 77) return "C+";
    if (pct >= 73) return "C";
    if (pct >= 70) return "C-";
    if (pct >= 67) return "D+";
    if (pct >= 60) return "D";
    return "F";
  }

  /** @param {{score:number,max_score?:number,is_excused?:boolean}} g @param {{max_score:number}} a */
  function maxScore(g, a) {
    return g.max_score != null ? g.max_score : a.max_score;
  }

  /**
   * gradesData: array of { grade, assignment, category|null }
   * categories: array with id, name, weight, drop_lowest
   */
  function simpleAverage(gradesData) {
    const scores = [];
    let totalPoints = 0;
    let totalPossible = 0;
    for (const { grade: g, assignment: a } of gradesData) {
      if (g.is_excused) continue;
      const maxS = maxScore(g, a);
      if (maxS > 0) scores.push((g.score / maxS) * 100);
      totalPoints += g.score;
      totalPossible += maxS;
    }
    const avg = scores.length ? scores.reduce((s, n) => s + n, 0) / scores.length : 0;
    return {
      average: Math.round(avg * 10) / 10,
      letter: toLetter(avg),
      total_points: Math.round(totalPoints * 10) / 10,
      total_possible: Math.round(totalPossible * 10) / 10,
      assignments_graded: scores.length,
    };
  }

  function weightedAverage(gradesData, categories) {
    const catGrades = {};
    for (const c of categories) catGrades[c.id] = [];
    const otherGrades = [];

    for (const { grade: g, assignment: a, category: c } of gradesData) {
      if (g.is_excused) continue;
      if (c && catGrades[c.id]) catGrades[c.id].push({ grade: g, assignment: a });
      else otherGrades.push({ grade: g, assignment: a });
    }

    let totalWeight = 0;
    let weightedSum = 0;
    const byCategory = {};

    for (const cat of categories) {
      let items = catGrades[cat.id] || [];
      if (!items.length) {
        byCategory[cat.name] = 0;
        continue;
      }
      items = items.slice().sort((x, y) => {
        const mx = maxScore(x.grade, x.assignment) || 1;
        const my = maxScore(y.grade, y.assignment) || 1;
        return x.grade.score / mx - y.grade.score / my;
      });
      const drop = cat.drop_lowest || 0;
      if (drop > 0) items = items.slice(drop);

      const scores = [];
      for (const { grade: g, assignment: a } of items) {
        const maxS = maxScore(g, a);
        if (maxS > 0) scores.push((g.score / maxS) * 100);
      }
      const catAvg = scores.length ? scores.reduce((s, n) => s + n, 0) / scores.length : 0;
      byCategory[cat.name] = Math.round(catAvg * 10) / 10;
      weightedSum += catAvg * cat.weight;
      totalWeight += cat.weight;
    }

    let uncatAvg = 0;
    if (otherGrades.length) {
      const otherScores = [];
      for (const { grade: g, assignment: a } of otherGrades) {
        const maxS = maxScore(g, a);
        if (maxS > 0) otherScores.push((g.score / maxS) * 100);
      }
      uncatAvg = otherScores.length ? otherScores.reduce((s, n) => s + n, 0) / otherScores.length : 0;
    }

    let final;
    if (totalWeight > 0 && otherGrades.length) {
      final = (weightedSum + uncatAvg) / (totalWeight + 1.0);
    } else if (totalWeight > 0) {
      final = weightedSum / totalWeight;
    } else if (otherGrades.length) {
      return simpleAverage(gradesData);
    } else {
      final = weightedSum;
    }

    return {
      average: Math.round(final * 10) / 10,
      letter: toLetter(final),
      by_category: byCategory,
    };
  }

  /**
   * @param {object[]} categories
   * @param {object[]} gradesData — { grade, assignment, category|null }
   */
  function studentAverage(categories, gradesData) {
    const result = categories.length
      ? weightedAverage(gradesData, categories)
      : simpleAverage(gradesData);
    result.has_grades = gradesData.some(({ grade: g }) => !g.is_excused);
    return result;
  }

  /**
   * Build class overview from per-student average rows.
   * @param {{student_id:number,name:string,average:number,letter:string,has_grades:boolean}[]} averages
   */
  function classOverview(averages) {
    const sorted = averages.slice().sort((a, b) => b.average - a.average);
    const graded = sorted.filter((a) => a.has_grades);
    const gradeDist = { A: 0, B: 0, C: 0, D: 0, F: 0 };
    for (const a of graded) {
      const letter = a.letter.replace("+", "").replace("-", "");
      if (letter in gradeDist) gradeDist[letter] += 1;
    }
    const classAvg = graded.length
      ? graded.reduce((s, a) => s + a.average, 0) / graded.length
      : 0;
    return {
      student_count: averages.length,
      class_average: Math.round(classAvg * 10) / 10,
      grade_distribution: gradeDist,
      top_performer: graded[0] || null,
      needs_support: graded.filter((a) => a.average < 70),
    };
  }

  /** Derive weight_pct from raw weight fractions (matches grades.py list_categories). */
  function withWeightPct(categories) {
    const total = categories.reduce((s, c) => s + (c.weight || 0), 0) || 1;
    return categories.map((c) => ({
      ...c,
      weight_pct: Math.round((c.weight / total) * 1000) / 10,
    }));
  }

  global.GradeComputer = {
    toLetter,
    studentAverage,
    classOverview,
    withWeightPct,
    simpleAverage,
    weightedAverage,
  };
})(typeof window !== "undefined" ? window : globalThis);
