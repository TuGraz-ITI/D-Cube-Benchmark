# D-Cube: A Benchmark for Low-Power Wireless Systems #

D-Cube's PCB design files are published as open source hardware under [CC-BY-SA](license.md) ([online](https://creativecommons.org/licenses/by-sa/4.0/deed.en)) [here](https://github.com/TuGraz-ITI/D-Cube).
D-Cube allows to accurately evaluate and compare the performance of low-power wireless sensor nodes in terms of the end-to-end delay, reliability, and power consumption, as well as to graphically visualize their evolution in real-time.
This tool has been used to set-up the EWSN 2016, 2017 and 2018 dependability competitions.
* [EWSN 2016 Dependability Competition (Graz, Austria)](http://ewsn2016.tugraz.at/cms/index.php?id=49)  
* [EWSN 2017 Dependability Competition (Uppsala, Sweden)](http://www.ewsn2017.org/dependability-competition1.html)
* [EWSN 2018 Dependability Competition (Madrid, Spain)](https://ewsn2018.networks.imdea.org/competition-program.html)
* [EWSN 2019 Dependability Competition (Beijing, China)](http://ewsn2019.thss.tsinghua.edu.cn/competition-scenario.html)

A scientific paper about D-Cube was published at the 14th International Conference on Embedded Wireless Systems and Networks (EWSN), and is available [here](http://www.carloalbertoboano.com/documents/boano17competition.pdf). 
An scientific paper describing D-Cube's binary patching capability and explaining how to use D-Cube to benchmark low-power wireless systems was published at the 1st International Workshop on Benchmarking Cyber-Physical Networks and Systems (CPSBench), and can be downloaded [here](http://www.carloalbertoboano.com/documents/schuss18benchmark.pdf).  
A set of slides giving a brief overview of D-Cube's capabilities and architecture can be found [here](http://www.carloalbertoboano.com/documents/D-Cube_overview.pdf).  

## Deployment ##
The software-side components consist of three parts: the custom python front- and backend for user interaction (dcube-web + db container), the measurement part (influxdb + grafana container), and the message broker (rabbitmq container).
To enable quick deployments the included docker-compose.yml can be used to setup the server side stack using [docker-compose](https://docs.docker.com/compose/).

## Raspberry Pi ##
**TBD** D-Cube uses the [PREEMPT_RT](https://wiki.linuxfoundation.org/realtime/preempt_rt_versions) pachset and a custom kernel module and firwmare for [JamLab-NG](https://github.com/TuGraz-ITI/JamLab-NG).

## Infrastructure ##
D-Cube's relies on dhcp and ntp (ideally provided by a Raspberry Pi with attached GPS module) being available. We recommend using dnsmasq for a minimal installation of a dhcp server and chrony for the ntp server.
