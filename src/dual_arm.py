#######################################

# Main program for the dual arm setup #

#######################################

import rospy, sys, moveit_commander, yaml, tf, geometry_msgs.msg, os
from ar_track_alvar_msgs.msg import AlvarMarkers
from math import *
import numpy as np
from std_srvs.srv import Trigger, TriggerResponse
from kitting_station.srv import Robotont, RobotontResponse

book_positions = dict()
shelf_position = dict()
sections = list()
sections_in = list()
robotont = False

def BookPositionCallback(data):
    global book_positions, sections

    for marker in data.markers:
        if marker.id not in list(book_positions.keys()) and marker.id in sections:
            book_positions[marker.id] = marker.pose.pose

def GetShelfPosition():
    global shelf_position
    dir = os.path.dirname(__file__)
    rel_path = "./../yaml/shelf_position.yaml"
    abs_file_path = os.path.join(dir, rel_path)
    with open(abs_file_path) as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
        for i in range(len(data)):
            id = list(data[i].keys())[0]
            shelf_position[id] = geometry_msgs.msg.Pose()
            shelf_position[id].position.x = data[i][id]['position']['x']
            shelf_position[id].position.y = data[i][id]['position']['y']
            shelf_position[id].position.z = data[i][id]['position']['z']
            shelf_position[id].orientation.x = data[i][id]['orientation']['x']
            shelf_position[id].orientation.y = data[i][id]['orientation']['y']
            shelf_position[id].orientation.z = data[i][id]['orientation']['z']
            shelf_position[id].orientation.w = data[i][id]['orientation']['w']

def getCoordinates(id):
    markers_y = list()
    markers_x = list()
    for marker in list(shelf_position.keys()):
        markers_y.append(shelf_position[marker].position.y)
        markers_x.append(shelf_position[marker].position.x)

    # finding equation of the line on which shelf is located
    coeff = np.polyfit(markers_x, markers_y, 1)
    # print("Coeffs:", coeff)
    # finding the equation of the line on whish xArm7 will stop before putting the book
    dist = 0.2/sin(pi/2 - abs(atan(coeff[0])))
    # print("Dist, angle:", dist, atan(coeff[0]))
    b = coeff[1]-dist if coeff[1]>0 else coeff[1]+dist
    # print("b:", b)
    dist_2 = sqrt(abs(shelf_position[id].position.x**2+(shelf_position[id].position.y-b)**2-0.04))
    a = coeff[0]**2+1
    c = -dist_2**2
    x = [-sqrt(-4*a*c)/(2*a), sqrt(-4*a*c)/(2*a)]
    y = [coeff[0]*x[0]+b, coeff[0]*x[1]+b]
    r = list()
    for i in range(2):
        r.append(sqrt((shelf_position[id].position.x-x[i])**2 + (shelf_position[id].position.y-y[i])**2))
    i = 0 if abs(r[0]-0.2)<abs(r[1]-0.2) else 1
    # print(x[i], y[i])
    angle1 = atan(coeff[0])
    angle2 = atan2(b, 0) - atan2(y[i], x[i])
    angle3 = angle1 + angle2 #if coeff[0]<0 else abs(angle1) - abs(angle2)
    # print(angle1, angle2, angle3)
    return [x[i], y[i], angle3]

class DualArm(object):
    def __init__(self):
        moveit_commander.roscpp_initialize(sys.argv)
        self.robot = moveit_commander.RobotCommander()
        self.scene = moveit_commander.PlanningSceneInterface()
        self.L_xarm7 = moveit_commander.MoveGroupCommander("L_xarm7")
        self.L_gripper = moveit_commander.MoveGroupCommander("L_xarm_gripper")
        self.R_xarm7 = moveit_commander.MoveGroupCommander("R_xarm7")
        self.R_gripper = moveit_commander.MoveGroupCommander("R_xarm_gripper")
        rospy.loginfo('DUAL ARM: Initialization complete.')
    
    def xArm7ToBox(self, id):
        gripper_values = self.R_gripper.get_current_joint_values()
        gripper_values[0] = 0
        self.R_gripper.go(gripper_values, wait=True)

        current_pose = self.R_xarm7.get_current_pose().pose
        pose_goal = current_pose
        pose_goal.position.x = book_positions[id].position.x + 0.1
        pose_goal.position.y = book_positions[id].position.y 
        pose_goal.position.z = book_positions[id].position.z + 0.2
        self.R_xarm7.set_pose_target(pose_goal)
        plan_success, traj, planning_time, error_code = self.R_xarm7.plan()
        self.R_xarm7.execute(traj, wait=True)
        self.R_xarm7.clear_pose_targets()

        current_pose = self.R_xarm7.get_current_pose().pose
        current_pose.position.z -= 0.09
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.R_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.R_xarm7.execute(traj, wait=True)
        self.R_xarm7.clear_pose_targets()

        gripper_values = self.R_gripper.get_current_joint_values()
        gripper_values[0] = 0.6 if id==6 else 0.8
        self.R_gripper.go(gripper_values, wait=True)

        current_pose = self.R_xarm7.get_current_pose().pose
        current_pose.position.z += 0.2
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.R_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.R_xarm7.execute(traj, wait=True)
        self.R_xarm7.clear_pose_targets()

    def PassTheBook(self, id):
        joint_goal = self.R_xarm7.get_current_joint_values()
        joint_goal[0] = -1.0472
        joint_goal[1] = 0
        joint_goal[2] = 0
        joint_goal[3] = 0
        joint_goal[4] = 0
        joint_goal[5] = -1.571
        joint_goal[6] = 0
        self.R_xarm7.go(joint_goal, wait=True)

        current_pose = self.R_xarm7.get_current_pose().pose
        current_pose.position.z = current_pose.position.z + 0.3
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.R_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.R_xarm7.execute(traj, wait=True)
        self.R_xarm7.clear_pose_targets()

        current_pose = self.R_xarm7.get_current_pose().pose
        current_pose.position.y = current_pose.position.y + 0.2
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.R_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.R_xarm7.execute(traj, wait=True)
        self.R_xarm7.clear_pose_targets()

        joint_goal = self.L_xarm7.get_current_joint_values()
        joint_goal[0] = 1.571
        joint_goal[1] = 0
        joint_goal[2] = 0
        joint_goal[3] = 0
        joint_goal[4] = 0
        joint_goal[5] = -1.571
        joint_goal[6] = 0
        self.L_xarm7.go(joint_goal, wait=True)

        L_pose_goal = self.L_xarm7.get_current_pose().pose
        R_current_pose = self.R_xarm7.get_current_pose().pose
        L_pose_goal.position.x = R_current_pose.position.x
        L_pose_goal.position.y = R_current_pose.position.y - 0.2
        L_pose_goal.position.z = R_current_pose.position.z
        waypoints = list()
        waypoints.append(L_pose_goal)
        (traj, fraction) = self.L_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

        L_current_pose = self.L_xarm7.get_current_pose().pose
        L_pose_goal = L_current_pose
        L_pose_goal.position.y = L_current_pose.position.y + 0.15
        waypoints = list()
        waypoints.append(L_pose_goal)
        (traj, fraction) = self.L_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

        L_gripper_values = self.L_gripper.get_current_joint_values()
        L_gripper_values[0] = 0.6 if id==6 else 0.8
        self.L_gripper.go(L_gripper_values, wait=True)

        R_gripper_values = self.R_gripper.get_current_joint_values()
        R_gripper_values[0] = 0
        self.R_gripper.go(R_gripper_values, wait=True)

        L_current_pose = self.L_xarm7.get_current_pose().pose
        L_pose_goal = L_current_pose
        L_pose_goal.position.y = L_current_pose.position.y - 0.2
        waypoints = list()
        waypoints.append(L_pose_goal)
        (traj, fraction) = self.L_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

    def xArm7ToShelf(self, id):
        joint_goal = self.L_xarm7.get_current_joint_values()
        joint_goal[0] = atan2(shelf_position[id].position.y, shelf_position[id].position.x)
        joint_goal[1] = 0
        joint_goal[2] = 0
        joint_goal[3] = 0
        joint_goal[4] = 0
        joint_goal[5] = -1.571
        joint_goal[6] = 0
        self.L_xarm7.go(joint_goal, wait=True)

        current_pose = self.L_xarm7.get_current_pose().pose
        current_pose.position.z = shelf_position[id].position.z + 0.1
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.L_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

        coords = getCoordinates(id)
        pose_goal = current_pose
        pose_goal.position.x = coords[0]
        pose_goal.position.y = coords[1]

        quaternion1 = (
        current_pose.orientation.x,
        current_pose.orientation.y,
        current_pose.orientation.z,
        current_pose.orientation.w)
        quaternion2 = tf.transformations.quaternion_from_euler(coords[2], 0, 0)
        quaternion = tf.transformations.quaternion_multiply(quaternion1, quaternion2)

        pose_goal.orientation.x = quaternion[0]
        pose_goal.orientation.y = quaternion[1]
        pose_goal.orientation.z = quaternion[2]
        pose_goal.orientation.w = quaternion[3]

        self.L_xarm7.set_pose_target(pose_goal)
        plan_success, traj, planning_time, error_code = self.L_xarm7.plan()
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

        current_pose = self.L_xarm7.get_current_pose().pose
        current_pose.position.x = shelf_position[id].position.x
        current_pose.position.y = shelf_position[id].position.y
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.L_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

        gripper_values = self.L_gripper.get_current_joint_values()
        gripper_values[0] = 0
        self.L_gripper.go(gripper_values, wait=True)

        current_pose = self.L_xarm7.get_current_pose().pose
        current_pose.position.x = coords[0]
        current_pose.position.y = coords[1]
        waypoints = list()
        waypoints.append(current_pose)
        (traj, fraction) = self.L_xarm7.compute_cartesian_path(waypoints, 0.01, 0.0)
        self.L_xarm7.execute(traj, wait=True)
        self.L_xarm7.clear_pose_targets()

        joint_goal = self.L_xarm7.get_current_joint_values()
        joint_goal[0] = atan2(shelf_position[id].position.y, shelf_position[id].position.x)
        joint_goal[1] = 0
        joint_goal[2] = 0
        joint_goal[3] = 0
        joint_goal[4] = 0
        joint_goal[5] = -1.571
        joint_goal[6] = 0
        self.L_xarm7.go(joint_goal, wait=True)

    def xArm7ToStart(self, arm):
        joint_goal = self.L_xarm7.get_current_joint_values()
        joint_goal[0] = 0
        joint_goal[1] = -0.68
        joint_goal[2] = 0
        joint_goal[3] = 0.83
        joint_goal[4] = 0
        joint_goal[5] = 1.5
        joint_goal[6] = 0
        if arm == "LR":
            self.L_xarm7.go(joint_goal, wait=True)
            joint_goal[0] = 0.5236
            self.R_xarm7.go(joint_goal, wait=True)
            gripper_values = self.L_gripper.get_current_joint_values()
            gripper_values[0] = 0
            self.L_gripper.go(gripper_values, wait=True)
            self.R_gripper.go(gripper_values, wait=True)
        elif arm == "L":
            self.L_xarm7.go(joint_goal, wait=True)
        elif arm == "R":
            joint_goal[0] = 0.5236
            self.R_xarm7.go(joint_goal, wait=True)

def mainProgramme(req):
    global sections
    sections = req.req
    while not rospy.is_shutdown():
        if set(book_positions.keys()) == set(sections):
            rospy.loginfo('DUAL ARM: Found box.')
            for id in sections:
                rospy.loginfo(f'DUAL ARM: Going for a book {id}.')
                coords = getCoordinates(id)

                move.xArm7ToBox(id)
                move.PassTheBook(id)
                move.xArm7ToStart("R")

                move.xArm7ToShelf(id)
                move.xArm7ToStart("L")
                if rospy.is_shutdown(): break
            rospy.loginfo('DUAL ARM: Done.')
            break
        else:
            move.xArm7ToStart("LR")
            rospy.loginfo('DUAL ARM: There is no box.')

    return RobotontResponse(success=True)

def mainProgrammeStart(req):
    global move, robotont
    rospy.loginfo('DUAL ARM: Got request.')
    GetShelfPosition()
    move = DualArm()
    move.xArm7ToStart("LR")
    rospy.loginfo('DUAL ARM: Going to start position.')
    robotont = True
    return TriggerResponse(success=True)

def main():
    rospy.init_node('dual_arm', anonymous=True)
    rospy.Subscriber("arm_2/ar_tf_marker", AlvarMarkers, BookPositionCallback)
    s = rospy.Service('main', Trigger, mainProgrammeStart)
    rospy.loginfo('DUAL ARM: Waiting for request.')
    while not rospy.is_shutdown():
        if robotont:
            robotont_serv = rospy.Service('robotont', Robotont, mainProgramme)
            rospy.loginfo('DUAL ARM: Waiting for robotont to come.')
            break
    rospy.spin()  

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass