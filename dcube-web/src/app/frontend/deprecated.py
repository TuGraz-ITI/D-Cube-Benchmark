@frontend.route('/admin/leaderboard/')
@roles_required("admins")
def admin_leaderboard():
    metrics = Metric.query

    coeff_rel = request.args.get("coeff_rel")
    if (coeff_rel == None):
        coeff_rel = 1.0
    else:
        coeff_rel = float(coeff_rel)

    coeff_energy = request.args.get("coeff_energy")
    if (coeff_energy == None):
        coeff_energy = 1.0
    else:
        coeff_energy = float(coeff_energy)

    coeff_latency = request.args.get("coeff_latency")
    if (coeff_latency == None):
        coeff_latency = 1.0
    else:
        coeff_latency = float(coeff_latency)

    jamming = request.args.get("jamming")
    if (jamming == None):
        jamming = 2
    else:
        jamming = int(jamming)

    count = request.args.get("count")
    if (count == None):
        count = 0
    else:
        count = int(count)

    duration = request.args.get("duration")
    if (duration == None):
        duration = Config.get_int("default_duration", 300)
    if not duration == "any":
        metrics = metrics.filter(Metric.job.has(Job.duration == int(duration)))

#    metrics=metrics.filter(Metric.job.has(Job.duration==4200))
    metrics = metrics.filter(Metric.job.has(Job.logs == False))
#    metrics=metrics.filter(Metric.job!=None).filter(Metric.latency!=None).filter(Metric.reliability!=None).filter(Metric.reliability<=1).filter(Metric.reliability>0.5)
    metrics = metrics.filter(Metric.job.has(Job.jamming == jamming))

    metrics = metrics.filter(Metric.job.has(Job.id > FIRST_JOB)).join(Job).join(Group).add_columns(
        Group.name).join(Firmware).add_columns(Firmware.name.label("filename")).add_columns(Job.description)

    df = pd.read_sql(metrics.statement, metrics.session.bind)
    df = df.dropna()

    df['latency'] = df['latency']/1000
    # df['reliability']=df['reliability']*100

    min_energy = df['energy'].min()
    min_latency = df['latency'].min()
    max_reliability = df['reliability'].max()

    df['rel_energy'] = (df['energy']-min_energy)/min_energy*coeff_energy
    df['rel_latency'] = (df['latency']-min_latency)/min_latency*coeff_latency
    df['rel_reliability'] = (
        max_reliability-df['reliability'])/max_reliability*coeff_rel

    df['total'] = df['rel_energy']+df['rel_latency']+df['rel_reliability']
    df = df.sort_values("total")

    if not (count == 0):
        df = df.groupby("description").head(count).reset_index(drop=True)

    jamming_max = Config.get_int("jamming_max", 0)

    durations_string = Config.get_string("durations", "30 60 120 180 300")
    durations = map(int, durations_string.split())

    return render_template('admin/leaderboard.html', df=df, jamming_max=jamming_max, jamming=jamming, count=count, min_energy=min_energy, min_latency=min_latency,
                           max_reliability=max_reliability, coeff_energy=coeff_energy, coeff_rel=coeff_rel, coeff_latency=coeff_latency, durations=durations, default_duration=duration)


@frontend.route('/editor/jamming_config')
@roles_required("admins")
def jamming_config_editor():
    return render_template('jamming_config_table.html')


@frontend.route('/editor/jamming_config/json/load')
@roles_required("admins")
def jamming_config_editor_load():
    jc = JammingConfig.query.all()
    return jsonify(json_list=[e.serialize for e in jc])


@frontend.route('/editor/jamming_timing')
@roles_required("admins")
def jamming_timing_editor():
    return render_template('jamming_timing_table.html')


@frontend.route('/editor/jamming_timing/json/load')
@roles_required("admins")
def jamming_timing_editor_load():
    jt = JammingTiming.query.all()
    return jsonify(json_list=[e.serialize for e in jt])


@frontend.route('/editor/jamming_scenario')
@roles_required("admins")
def jamming_scenario_editor():
    return render_template('jamming_scenario_table.html')


@frontend.route('/editor/jamming_scenario/json/load')
@roles_required("admins")
def jamming_scenario_editor_load():
    js = JammingScenario.query.all()
    return jsonify(json_list=[e.serialize for e in js])


@frontend.route('/editor/jamming_pi')
@roles_required("admins")
def jamming_pi_editor():
    return render_template('jamming_pi_table.html')


@frontend.route('/editor/jamming_pi/json/load')
@roles_required("admins")
def jamming_pi_editor_load():
    jp = JammingPi.query.all()
    return jsonify(json_list=[e.serialize for e in jp])


@frontend.route('/editor/jamming_composition')
@roles_required("admins")
def jamming_composition_editor():
    return render_template('jamming_composition_table.html')


@frontend.route('/editor/jamming_composition/json/load')
@roles_required("admins")
def jamming_composition_editor_load():
    jc = JammingComposition.query.all()
    return jsonify(json_list=[e.serialize for e in jc])


@frontend.route('/editor/layout_pi')
@roles_required("admins")
def layout_pi_editor():
    return render_template('layout_pi_table.html')


@frontend.route('/editor/layout_pi/json/load')
@roles_required("admins")
def layout_pi_editor_load():
    lp = LayoutPi.query.all()
    return jsonify(json_list=[e.serialize for e in lp])


@frontend.route('/editor/layout_composition')
@roles_required("admins")
def layout_composition_editor():
    return render_template('layout_composition_table.html')


@frontend.route('/editor/layout_composition/json/load')
@roles_required("admins")
def layout_composition_editor_load():
    lc = LayoutComposition.query.all()
    return jsonify(json_list=[e.serialize for e in lc])
