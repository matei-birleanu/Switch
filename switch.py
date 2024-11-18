#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    while True:
        # TODO Send BDPU every second if necessary
        time.sleep(1)
def parse_config_file(path,id):
    results = {}
    full_path = path + id + ".cfg"
    f = open(full_path, 'r')
    next(f)
    count = 0
    for line in f:
        interf = count
        count = count + 1
        line = line.split()
        if len(line) > 1 and line[1].isdigit:
            vlan_id = line[1]
        else:
            vlan_id = 'T'
        results[interf] = vlan_id
    return results  

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))   
    mac_table = {}
    config_map = {}
    path = "/home/matei/Desktop/Tema1RL/tema1-public/configs/switch"
    config_map = parse_config_file(path,switch_id)
    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()
        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)
        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]
        mac_table[src_mac] = interface
        # TODO: Implement forwarding with learning
        enter = interface
        v_id = config_map[interface]
        new_data = data[0:12] + data[16:]
        if v_id != 'T':
            data_tag = data[0:12] + create_vlan_tag(int(v_id)) + data[12:]        
        if dest_mac != 'ff:ff:ff:ff':##unicast
            if dest_mac in mac_table: ## am in tabela
                if v_id != 'T': ## am in tabela si vine de pe port access
                    x = mac_table[dest_mac]
                    y = config_map[x]
                    if y != 'T' and  y == v_id and x != enter:
                        send_to_link(x,length,data)
                    if y == 'T':
                        send_to_link(x,length + 4,data_tag)   
                if v_id == 'T': ## am in tabela si vine de pe port trunk
                    x = mac_table[dest_mac]
                    y = config_map[x]
                    ## x interfata y vlanid
                    if y == 'T' and x != enter: ## tot pe trunk doar il dau mai departe
                            send_to_link(x,length,data)
                    if y != 'T' and vlan_id == int(y):
                        send_to_link(x,length - 4, new_data)
            else: ## nu am rezultat in tabela mac
                if v_id == 'T': ## primesc de pe port trunk
                    for x,y in config_map.items():## x -> interfata y -> vlanid
                        if y == 'T' and x != enter:
                            send_to_link(x,length,data)
                        elif  y != 'T' and int(y) == vlan_id and x != enter:
                                send_to_link(x,length - 4, new_data)
                if v_id != 'T': ## primesc de pe port access
                    for x,y in config_map.items():## x -> interfata y -> vlanid
                        if y == 'T':
                            send_to_link(x,length + 4,data_tag)
                        if y != 'T' and x != enter and y == v_id:
                            send_to_link(x,length,data)
        else:##multicast
            if v_id != 'T': ## primesc de pe port access
                for x,y in config_map.items():## x -> interfata y -> vlanid
                  if enter != x and y != 'T' and v_id == y:
                      send_to_link(x,length,data)
                  elif y == 'T':
                      send_to_link(x,length + 4, data_tag)
            if v_id == 'T':## primesc de pe port trunk
                for x,y in config_map.items():## x -> interfata y -> vlanid
                    if y == 'T' and enter != x:
                        send_to_link(x,length,data)
                    if y != 'T':
                          if y == v_id:
                            send_to_link(x,new_data,length - 4)
        
        # TODO: Implement STP support

        # data is of type bytes.
        # send_to_link(i, length, data)

if __name__ == "__main__":
    main()
