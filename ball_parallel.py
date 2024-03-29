# MONTE CARLO SIMULATION EINES BALLWURFS, LOKAL
#
import threading
import time
import socket
import dispy
import numpy

from progressbar import print_progress


# Trajektorie eines geworfenen Balls
def trajectory(v_init_0, a_init_0, h_init_0, v_air_0, n=1):
    import random, math

    # Konstanten
    g = 9.81  # Gravitationskonstante [m/s^2]
    cw = 0.2  # Strömungswiderstandskoeffizient [-]
    rho = 1.2  # Luftdichte [kg/m^3]
    d = 0.068  # Balldurchmesser [m]
    m = 0.057  # Ballmassen [kg]
    dt = 0.1  # Schrittweite [s]

    # Luftwiderstand (Wert und Richtung)
    def air_drag(v_x, v_y, v_air, rho_l):
        import math
        f_a = 0.5 * rho_l * (math.pow(v_x + v_air, 2) + math.pow(v_y, 2)) * math.pow(d, 2) * math.pi / 4
        a_a = math.atan2(v_y, v_x + v_air)
        return f_a, a_a

    result = list()

    for i in range(0, n):
        # Füge Unsicherheit hinzu
        v_init = v_init_0 + (random.random() - .5) * 2.0
        a_init = a_init_0 + (random.random() - .5) * 4.0
        h_init = h_init_0 + (random.random() - .5) * 0.1
        v_air = v_air_0 + max(0.0, (random.random() - .5) * 2.0)
        rho_l = rho * (1 + (random.random() - .5) * 0.2)

        # Initialisierung
        r_x = 0
        r_y = h_init
        v_x = v_init * math.cos(a_init * math.pi / 180.0)
        v_y = v_init * math.sin(a_init * math.pi / 180.0)

        # Indikator ob der Ball die Nulllinie von unten noch nicht geschnitten hat
        h_low = 0 > r_y

        # Euler-vorwärts-Integration
        # ... solange bis der Ball die Nullinie von oben schneidet

        ite = 0

        while (h_low or 0 < r_y) and ite < 100000:
            (f_a, b_a) = air_drag(v_x, v_y, v_air, rho_l)

            a_x = -f_a * math.cos(b_a)
            a_y = -m * g - f_a * math.sin(b_a)

            r_x += v_x * dt
            r_y += v_y * dt
            v_x += a_x * dt
            v_y += a_y * dt

            if h_low:
                h_low = 0 >= r_y

            ite += 1

        result.append(r_x)

    return result


# Zählt die Distanzen
def count_distances(d):
    d = numpy.around(d)
    b = numpy.linspace(min(d), max(d), 15)
    hist = {}
    for i in d:
        idx = find_nearest(b, i)
        hist[idx] = hist.get(idx, 0) + 1
    return hist


# Findet den nächsten Wert in einem Array
def find_nearest(array, value):
    array = numpy.asarray(array)
    idx = (numpy.abs(array - value)).argmin()
    return array[idx]


# Histogramm in der Konsole
def histogram(d):
    c = count_distances(d)
    dist_count = len(d)

    for k in sorted(c):
        print('\t{0:5.0f} m | {1}'.format(k, '+' * int(c[k] * 500 / dist_count)))


# Job callback für dispy
def job_callback(job):  # executed at the client
    global pending_jobs, jobs_cond, no_of_jobs_finished, n_runs
    global distance, lower_bound
    global n_sim_per_run

    if (job.status == dispy.DispyJob.Finished  # most usual case
            or job.status in (dispy.DispyJob.Terminated, dispy.DispyJob.Cancelled,
                              dispy.DispyJob.Abandoned)):
        # 'pending_jobs' is shared between two threads, so access it with
        # 'jobs_cond' (see below)
        jobs_cond.acquire()
        no_of_jobs_finished = no_of_jobs_finished + 1
        if job.id:  # job may have finished before 'main' assigned id
            pending_jobs.pop(job.id)
            if no_of_jobs_finished % 1 == 0:
                print_progress(no_of_jobs_finished, n_runs / n_sim_per_run, prefix='Fortschritt:', suffix='komplett',
                               length=50)

            # extract the results for each job as it happens
            dist_results = job.result  # returns results from job
            distance = distance + dist_results

            if len(pending_jobs) <= lower_bound:
                jobs_cond.notify()

        jobs_cond.release()


if __name__ == '__main__':

    # set lower and upper bounds as appropriate
    # lower_bound is at least num of cpus and upper_bound is roughly 3x lower_bound
    lower_bound, upper_bound = 13 * 4, 3 * 13 * 4

    v_init = 8.0  # Initiale Geschwindigkeit [m/s]
    a_init = 40.0  # Abwurfwinkel [°]
    h_init = 2.0  # Abwurfhöhe [m]
    v_air = 5.0  # Windgeschwindigkeit [m/s]
    n_runs = 100  # Läufe [-]

    n_sim_per_run = 50

    server_nodes = ["192.168.0.101",
                    "192.168.0.102",
                    "192.168.0.103",
                    "192.168.0.104",
                    "192.168.0.105",
                    "192.168.0.106",
                    "192.168.0.107",
                    "192.168.0.108",
                    "192.168.0.109",
                    "192.168.0.110",
                    "192.168.0.111",
                    "192.168.0.112",
                    "192.168.0.113",
                    "192.168.0.114",
                    "192.168.0.115",
                    "192.168.0.116"]
    master_node = '192.168.0.116'

    # use Condition variable to protect access to pending_jobs, as
    # 'job_callback' is executed in another thread
    jobs_cond = threading.Condition()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))  # doesn't matter if 8.8.8.8 can't be reached

    # TODO: erstellen Sie einen Cluster, welcher die Funktion 'trajectory' parallel ausführen kann
    cluster = None

    pending_jobs = {}
    no_of_jobs_finished = 0

    print(('Schätze die Wurfdistanz eines Balls (Total %s Läufe):' % n_runs))
    print('  Initiale Geschwindigkeit: %s m/s' % v_init)
    print('  Abwurfwinkel:             %s°' % a_init)
    print('  Abwurfhöhe:               %s m' % h_init)
    print('  Windgeschwindigkeit:      %s m/s' % v_air)
    total_inside = 0
    print_progress(0, 1, prefix='Fortschritt:', suffix='komplett', length=50)

    i = 0

    distance = list()

    start = time.time()
    while i < n_runs and (time.time() - start) <= 60:
        n_sims = min(n_runs - i, n_sim_per_run)
        i += n_sims

        # schedule execution of 'compute' on a node (running 'dispynode')
        # TODO: Erstellen Sie einen neuen Job für den Cluster, welcher die Notwendigen Parameter übergibt
        # Tip: Notwendige Parameter sind v_init, a_init, h_init, v_air, n_sims
        job = None

        jobs_cond.acquire()

        job.id = i  # associate an ID to the job

        # there is a chance the job may have finished and job_callback called by
        # this time, so put it in 'pending_jobs' only if job is pending
        if job.status == dispy.DispyJob.Created or job.status == dispy.DispyJob.Running:
            pending_jobs[i] = job
            # dispy.logger.info('job "%s" submitted: %s', i, len(pending_jobs))
            if len(pending_jobs) >= upper_bound:
                while len(pending_jobs) > lower_bound:
                    jobs_cond.wait()
        jobs_cond.release()

    cluster.wait(timeout=30)

    end = time.time()

    time.sleep(1)

    # Berechnet die Schätzung für pi
    print(('Simulation der Wurfdistanz mit %s Läufen:' % n_runs))
    histogram(distance)
    print(('Mittelwert: %5.2f m' % (numpy.mean(distance))))
    print(('Laufzeit: %s s' % (end - start)))

    cluster.print_status()
    cluster.close(timeout=15, terminate=True)
