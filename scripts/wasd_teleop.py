#!/usr/bin/env python3
"""WASD / arrow-key teleop for TurtleBot3 in Gazebo (ROS 2, TwistStamped on /cmd_vel).

Hold a key to move, release it and the robot stops.
Run:  python3 wasd_teleop.py
"""
import os
import select
import sys
import termios
import time
import tty

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node

HELP = """
WASD / arrow keys teleop  -  hold a key to move, release to stop
----------------------------------------------------------------
  W or Up    : forward        S or Down  : backward
  A or Left  : turn left      D or Right : turn right
  Q / E      : forward + turn left / right
  Space      : stop now       + / -      : faster / slower
  Ctrl+C     : quit
(AZERTY keyboard? Z also works as forward.)
"""

# key -> (linear direction, angular direction)
KEYS = {
    'w': (1, 0), 'z': (1, 0), 'UP': (1, 0),
    's': (-1, 0), 'DOWN': (-1, 0),
    'a': (0, 1), 'LEFT': (0, 1),
    'd': (0, -1), 'RIGHT': (0, -1),
    'q': (1, 1), 'e': (1, -1),
}
ARROWS = {b'A': 'UP', b'B': 'DOWN', b'C': 'RIGHT', b'D': 'LEFT'}

MAX_LIN = 0.26   # m/s   (TurtleBot3 Waffle limit)
MAX_ANG = 1.8    # rad/s
RELEASE_TIMEOUT = 0.6  # s without a key press = key released


def read_key(fd):
    """Return one key as a string ('w', 'UP', ...) or None."""
    ch = os.read(fd, 1)
    if not ch:
        return None
    if ch == b'\x1b':  # arrow keys arrive as ESC [ A/B/C/D
        if select.select([fd], [], [], 0.01)[0] and os.read(fd, 1) == b'[':
            if select.select([fd], [], [], 0.01)[0]:
                return ARROWS.get(os.read(fd, 1))
        return None
    return ch.decode(errors='ignore').lower() or None


def main():
    rclpy.init()
    node = Node('wasd_teleop')
    pub = node.create_publisher(TwistStamped, 'cmd_vel', 10)

    fd = sys.stdin.fileno()
    lin, ang = 0.20, 0.8
    cmd = (0, 0)
    last_key = 0.0
    shown = None
    settings = termios.tcgetattr(fd)

    def publish(lx, az):
        msg = TwistStamped()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = float(lx)
        msg.twist.angular.z = float(az)
        pub.publish(msg)

    print(HELP)
    print(f'speed {lin:.2f} m/s   turn {ang:.2f} rad/s')
    try:
        tty.setcbreak(fd)
        while rclpy.ok():
            if select.select([fd], [], [], 0.05)[0]:
                key = read_key(fd)
                if key in KEYS:
                    cmd = KEYS[key]
                    last_key = time.time()
                elif key == ' ':
                    cmd = (0, 0)
                elif key in ('+', '='):
                    lin, ang = min(lin + 0.02, MAX_LIN), min(ang + 0.1, MAX_ANG)
                    print(f'speed {lin:.2f} m/s   turn {ang:.2f} rad/s')
                elif key in ('-', '_'):
                    lin, ang = max(lin - 0.02, 0.02), max(ang - 0.1, 0.1)
                    print(f'speed {lin:.2f} m/s   turn {ang:.2f} rad/s')
            if time.time() - last_key > RELEASE_TIMEOUT:
                cmd = (0, 0)
            lx, az = cmd[0] * lin, cmd[1] * ang
            publish(lx, az)
            state = (lx, az)
            if state != shown:  # live status line
                sys.stdout.write(f'\rsending: linear {lx:+.2f} m/s  angular {az:+.2f} rad/s   ')
                sys.stdout.flush()
                shown = state
    except KeyboardInterrupt:
        pass
    finally:
        publish(0.0, 0.0)
        termios.tcsetattr(fd, termios.TCSADRAIN, settings)
        print()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
