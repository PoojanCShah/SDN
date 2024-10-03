from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology.api import get_all_link, get_all_switch
from collections import defaultdict
from ryu.topology import event
import copy

class Tree(app_manager.RyuApp):
    
    # Set the OpenFlowProtocol Version
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(Tree,self).__init__(*args,  **kwargs)
        self.nodes = []
        self.links = []
        self.graph = defaultdict(list)
        self.tree = defaultdict(list)
        self.raw_nodes = {}
        self.raw_links = {}
        self.inactive_ports = defaultdict(list)
        self.mac_to_port = {}
        self.macs = []

        
        
    '''
    Decorator for when a switch enters the topology
    Notice that we use ryu.topologu.event.EventSwitchEnter
    '''

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        
        raw_nodes = copy.copy(get_all_switch(self))
        raw_links = copy.copy(get_all_link(self))
        
        # Rebuild the Network Topology
        
        self.nodes = []
        self.links = []
        self.graph = defaultdict(list)
        self.raw_nodes = {}
        self.raw_links = {}
 
        
        for raw_node in raw_nodes : 
            node = raw_node.dp.id
            self.nodes.append(node)
            self.raw_nodes[node] = raw_nodes
            

        for raw_link in raw_links :
            u = raw_link.src.dpid
            v = raw_link.dst.dpid
            self.graph[u].append(v)
            self.graph[v].append(u)
            self.raw_links[(u,v)] = raw_link
            self.raw_links[(v,u)] = raw_link
            
        for n in self.nodes:
            self.graph[n] = list(set(self.graph[n]))
                
        self.compute_spanning_tree()
        
        
        
    '''
    Compute the Spanning Tree and Active ports Afresh
    '''
    def compute_spanning_tree(self):
        
        inactive_ports = defaultdict(list)
        spanning_tree = defaultdict(list)
        
        tree = []
        
        edges = []
        for u in self.nodes:
            for v in self.graph[u]:
                edges.append((u,v))
                
        

        visited = {}
        
        for n in self.nodes:
            visited[n] = False
            
        for root in self.nodes:
            if not visited[root]:
                queue = []
                queue.append(root)
                visited[root] = True
                
                while queue:
                    u = queue.pop(0)
                    for v in self.graph[u]:
                        if not visited[v]:
                            queue.append(v)
                            visited[v] = True
                            tree.append((u,v))
                            tree.append((v,u))
                            
        for edge in tree:
            raw_link = self.raw_links[edge]
            
            src = raw_link.src.dpid
            dst = raw_link.dst.dpid
            
            spanning_tree[src].append(dst)
            spanning_tree[dst].append(src)
            
            src_port = raw_link.src.port_no
            dst_port = raw_link.dst.port_no
            
            
        for edge in edges :
            if edge not in tree:
                
                raw_link = self.raw_links[edge]
            
                src = raw_link.src.dpid
            
                dst = raw_link.dst.dpid
            
                src_port = raw_link.src.port_no
                dst_port = raw_link.dst.port_no
            
                inactive_ports[src].append(src_port)
                inactive_ports[dst].append(dst_port)
            
        for n in self.nodes:
            inactive_ports[n] = list(set(inactive_ports[n])) 
            spanning_tree[n] = list(set(spanning_tree[n]))   
            
        self.inactive_ports = inactive_ports
        self.tree = spanning_tree
        print(self.inactive_ports)
            
        self.dump_info()
        
        
        
    def dump_info(self):
        with open("topo.csv", "w") as f:
            f.write("TopoGraph------------------------------------------------\n")
            for n in self.nodes:
                f.write(f"{n} : {self.graph[n]}\n")
            f.write("SpanningTree---------------------------------------------\n")
            for n in self.nodes:
                f.write(f"{n} : {self.tree[n]}\n")
            f.write("inActivePorts----------------------------------------------\n")
            for n in self.nodes:
                f.write(f"{n} : {self.inactive_ports[n]}\n")
            f.write("Links-----------------------------------------------------\n")
            for l in self.raw_links:
                print(l)
                f.write(str(self.raw_links[l])+ "\n")
                
                
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        switch = msg.datapath
        ofproto = switch.ofproto
        parser = switch.ofproto_parser
        
        id = switch.id
        
        self.mac_to_port.setdefault(id,{})
        
        print(self.mac_to_port)
        
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)
        src = eth_pkt.src 
        dst = eth_pkt.dst

        self.macs.append(src)
        self.macs.append(dst)
        
        print(list(set(self.macs)))
        
        in_port = msg.match["in_port"]
        self.logger.info("packet in %s %s %s %s", id, src, dst, in_port)
        
        
        
        print(f"port = {in_port} , active ports = {self.inactive_ports[id]}")
        
        if in_port not in self.inactive_ports[id]  :
            
            self.mac_to_port[id][src] = in_port
            
            if dst in self.mac_to_port[id]:
                print("FFFFFFFFFFFFFUUUUUUUUUUUCCCCCCCCCCCKKKKKKK")
                out_port = self.mac_to_port[id][dst]
                actions = [parser.OFPActionOutput(out_port)]
                
                match = parser.OFPMatch(in_port = in_port, eth_dst = dst)
                self.add_flow(switch, 1, match, actions)
                    
                out = parser.OFPPacketOut(datapath = switch, buffer_id = ofproto.OFP_NO_BUFFER, in_port = in_port, actions = actions, data = msg.data)
                switch.send_msg(out)
                
                
            
            else :
                actions = []
                for out_port in switch.ports :
                    
                    if not (out_port == in_port) and out_port not in self.inactive_ports[id] :
                    
                        actions.append(parser.OFPActionOutput(out_port))
                        
                        
            out = parser.OFPPacketOut(datapath = switch, buffer_id = ofproto.OFP_NO_BUFFER, in_port = in_port, actions = actions, data = msg.data)
            switch.send_msg(out)
            
        
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        
    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)
                  
            
            
    
              
        
                                
    
        
    

        
        