import itertools
import z3

player_to_index = {
    "Ben" : 0,
    "Seth" : 1,
    "Kevin T"  : 2,
    "Kevin P" : 3,
    "Abtin" : 4,
    "Sam" : 5,
    "Danny" : 6,
    "Nate" : 7,
    "Adam" : 8,
    "Brandon" : 9,
}   

current_wins = (10, 7,7,7,6,6,6,6,5,5)
current_points = (146426, 145224, 141226, 137248, 149036, 141716, 137510, 130564, 138424, 134000)
matchups = [
    (3, 4),
    (2, 9), 
    (7, 1),
    (8, 5),
    (0, 6),
]

def add_contraints():
    solver = z3.Solver()
    # variables for centipoints scored this week
    points = [z3.Int(f"points_{i}") for i in range(len(player_to_index))]
    # variables for total wins
    wins = [z3.Int(f"wins_{i}") for i in range(len(player_to_index))]
    # variable for final place
    place = [z3.Int(f"place_{i}") for i in range(len(player_to_index))]
    # assumme 50 < p < 200
    solver.add([z3.And(p >= 5000, p <= 20000) for p in points])
    # add a win if you beat your opponent
    for p1, p2 in matchups:
        solver.add(z3.If(points[p1] >= points[p2],
                         wins[p1] == current_wins[p1] + 1,
                         wins[p1] == current_wins[p1]))
        solver.add(z3.If(points[p2] > points[p1],
                         wins[p2] == current_wins[p2] + 1,
                         wins[p2] == current_wins[p2]))
    # disallow final point ties
    for i in range(len(player_to_index)):
        for j in range(i + 1, len(player_to_index)):
            solver.add(z3.And(points[i] + current_points[i] != points[j] + current_points[j]))
            solver.add(z3.And(points[i] != points[j]))
    # calculate place based on wins and points
    for i in range(len(player_to_index)):
        better_count = []
        for j in range(len(player_to_index)):
            if i == j:
                continue
            better = z3.Or(wins[j] > wins[i],
                           z3.And(wins[j] == wins[i],
                                  current_points[j] + points[j] > current_points[i] + points[i]))
            better_count.append(z3.If(better, 1, 0))
        solver.add(place[i] == 1 + z3.Sum(better_count))
    return solver, place, wins, points

def get_scenarios(player_place_list):
    solver, place, wins, points = add_contraints()
    for player, final_place in player_place_list:
        player_index = player_to_index[player]
        solver.add(place[player_index] <= final_place)
    scenarios = []
    while solver.check() == z3.sat:
        model = solver.model()
        scenario = {}
        for i in range(len(player_to_index)):
            scenario[i] = {
                "points": model[z3.Int(f"points_{i}")].as_long() / 100.0,
                "wins": model[z3.Int(f"wins_{i}")].as_long(),
                "place": model[z3.Int(f"place_{i}")].as_long(),
            }
        scenarios.append(scenario)
        # add constraint to avoid getting the same scenario again
        scenario_constraint = []
        for i in range(len(player_to_index)):
            scenario_constraint.append(
                z3.Int(f"place_{i}") != model[z3.Int(f"place_{i}")]
            )
            scenario_constraint.append(
                z3.Int(f"wins_{i}") != model[z3.Int(f"wins_{i}")] )

        solver.add(z3.Or(scenario_constraint))
    return scenarios

def get_matchup_outcomes(scenario, matchups, player_to_index):
    outcomes = [None] * len(matchups)
    for i, (p1, p2) in enumerate(matchups):
        p1_points = scenario[p1]["points"]
        p2_points = scenario[p2]["points"]
        if p1_points >= p2_points:
            outcomes[i] = 0
        else:
            outcomes[i] = 1
    return outcomes

def subsumes(existing, candidate):
    non_none_indices_existing = [i for i, v in enumerate(existing) if v is not None]
    if all(existing[i] == candidate[i] for i in non_none_indices_existing):
        return True
    return False

def search_for_sufficient_conditions(player_place_list, matchups):
    solver, place, wins, points = add_contraints()
    for player, final_place in player_place_list:
        player_index = player_to_index[player]
        solver.add(place[player_index] > final_place)
    outcome_sets = itertools.product([None, 0, 1], repeat=len(matchups))
    sufficient_conditions = []
    for outcomes in outcome_sets:
        if any(subsumes(existing, outcomes) for existing in sufficient_conditions):
            continue
        outcome_constraints = []
        for i, (p1, p2) in enumerate(matchups):
            if outcomes[i] == 0:
                outcome_constraints.append(
                    points[p1] >= points[p2]
                )
            elif outcomes[i] == 1:
                outcome_constraints.append(
                   points[p2] > points[p1]
                )
        solver.push()
        solver.add(outcome_constraints)
        if solver.check() == z3.unsat:
            sufficient_conditions.append(outcomes)
        solver.pop()
    return sufficient_conditions

def get_final_standings_table(scenario, player_to_index):
    standings = []
    index_to_player = {v: k for k, v in player_to_index.items()}
    for i in range(len(player_to_index)):
        player_name = index_to_player[i]
        total_points = current_points[i] + scenario[i]["points"]*100
        total_wins = scenario[i]["wins"]
        final_place = scenario[i]["place"]
        standings.append((final_place, player_name, total_wins, total_points))
    standings.sort()
    return standings

def get_necessary_outcomes(scenarios):
    necessary_outcomes = []
    for i in range(len(matchups)):
        outcome_set = set()
        for scenario in scenarios:
            outcomes = get_matchup_outcomes(scenario, matchups, player_to_index)
            outcome_set.add(outcomes[i])
        if len(outcome_set) == 1:
            necessary_outcomes.append(outcome_set.pop())
        else:
            necessary_outcomes.append(None)
    return necessary_outcomes

def analyze(player_name, threshold='playoffs'):
    if threshold == 'playoffs':
        final_place = 6
    elif threshold == 'bye':
        final_place = 2
    if threshold == 'playoffs':
        print(f"Analyzing scenarios for {player_name} to make the playoffs...")
    else:
        print(f"Analyzing scenarios for {player_name} to get a first round bye...")
    scenarios = get_scenarios([(player_name, final_place)])
    print(len(scenarios), "scenarios found.")
    if len(scenarios) == 0:
        print(f"Bummer, {player_name} cannot {'make the playoffs' if threshold == 'playoffs' else 'get a first round bye'} under any circumstances.")
        return
    necessary_outcomes = get_necessary_outcomes(scenarios)
    sufficient_conditions = search_for_sufficient_conditions([(player_name, final_place)], matchups)
    index_to_player = {v: k for k, v in player_to_index.items()}
    print(f"If these outcomes occur, then {player_name} is guaranteed to {'make the playoffs' if threshold == 'playoffs' else 'get a first round bye'}...")
    if not sufficient_conditions:
        print("  None found.")
    for i, cond in enumerate(sufficient_conditions):
        strings = []
        print(f" Case {i+1}:")
        for i, (p1, p2) in enumerate(matchups):
            outcome = cond[i]
            if outcome == 0:
                outcome_str = (f"   {index_to_player[p1]} wins vs {index_to_player[p2]}")
                strings.append(outcome_str)
            elif outcome == 1:
                outcome_str = (f"   {index_to_player[p2]} wins vs {index_to_player[p1]}")
                strings.append(outcome_str)
        if all(outcome is None for outcome in cond):
            strings.append("This is already guaranteed!")
            return
        full_str = " AND \n".join(strings)
        print(full_str)
    print(f"{player_name} needs these results to have a shot at {'making the playoffs' if threshold == 'playoffs' else 'getting a first round bye'}...")
    strings = []
    for i, (p1, p2) in enumerate(matchups):
        outcome = necessary_outcomes[i]
        if outcome == 0:
            outcome_str = (f"   {index_to_player[p1]} must win vs {index_to_player[p2]}")
            strings.append(outcome_str)
        elif outcome == 1:
            outcome_str = (f"   {index_to_player[p2]} must win vs {index_to_player[p1]}")
            strings.append(outcome_str)
    if not strings:
        print("   None found.")
    else:
        full_str = " AND \n".join(strings)
        print(full_str)
    print(f"Here's an example of scenario where {player_name} {'makes the playoffs' if threshold == 'playoffs' else 'gets a first round bye'}...")
    example_scenario = scenarios[0]
    outcomes = get_matchup_outcomes(example_scenario, matchups, player_to_index)
    print("Matchup outcomes:")
    for i, (p1, p2) in enumerate(matchups):
        outcome = outcomes[i]
        if outcome == 0:
            print(f"  {index_to_player[p1]} beats {index_to_player[p2]} ({example_scenario[p1]['points']} to {example_scenario[p2]['points']})")
        else:
            print(f"  {index_to_player[p2]} beats {index_to_player[p1]} ({example_scenario[p2]['points']} to {example_scenario[p1]['points']})")
    final_standings = get_final_standings_table(example_scenario, player_to_index)
    print("Final standings:")
    for place, player, wins, points in final_standings:
        print(f"  {place}. {player}: {wins} wins, {points/100:.2f} points")


if __name__ == "__main__":
    analyze("Brandon", threshold='playoffs')
