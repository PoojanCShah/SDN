from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.node import RemoteController, OVSSwitch

class CustomLoopTopo(Topo):
    def build(self):
        # Add switches
        num_switches = 5
        switches = []
        for i in range(1, num_switches + 1):
            switch = self.addSwitch(f's{i}')
            switches.append(switch)

        # Add hosts and connect them to switches
        hosts = []
        for i in range(1, 11):
            host = self.addHost(f'h{i}')
            hosts.append(host)
            # Connect first 5 hosts to the first 3 switches
            if i <= 5:
                self.addLink(host, switches[i % 3])
            # Connect remaining 5 hosts to the last 2 switches
            else:
                self.addLink(host, switches[(i % 2) + 3])

        # Add links between switches to create a looped network
        self.addLink(switches[0], switches[1])
        self.addLink(switches[1], switches[2])
        self.addLink(switches[2], switches[0])  # First loop between s1, s2, and s3

        self.addLink(switches[2], switches[3])
        self.addLink(switches[3], switches[4])
        self.addLink(switches[4], switches[2])  # Second loop between s3, s4, and s5

        # Add additional links between switches to create more redundancy (optional)
        self.addLink(switches[0], switches[4])  # Direct link between s1 and s5

def run():
    """Create the network, start it, and enter the CLI."""
    topo = CustomLoopTopo()
    net = Mininet(topo=topo, switch=OVSSwitch, build=False)
    net.addController('c0', controller=RemoteController, ip="127.0.0.1", protocol='tcp', port=6633)
    net.build()
    net.start()
    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    # Set log level to display Mininet output
    setLogLevel('info')
    run()
