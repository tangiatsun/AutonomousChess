#main code for the chess project. To run in the terminal, use the command:
#sudo -E python [filename]

# Modules
import time 
import RPi.GPIO as GPIO
import chess
import chess.engine
from threading import Thread
import multiprocessing

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

curr_state = 0
CW = 0
CCW = 1

#definitions, orientation when the extrusion pipe is on the top
down = (0,1)
up = (1,0)
left = (1,1)
right = (0,0)

#magnet detector pin declarations and current coordinates
encoder_x = 18
encoder_y = 25 
x_curr_coord = 0
y_curr_coord = 0

#setup as Input
GPIO.setup(encoder_x,GPIO.IN) 
GPIO.setup(encoder_y,GPIO.IN) 

#stepper motor pin declarations

#right
step_pin_1 = 27
direction_pin_1 = 17

#left
step_pin_2 = 13
direction_pin_2 = 6

#DC motor declarations
PWM_pin = 16
AIN1_pin = 20
AIN2_pin = 21

#pin declarations for 8 to 1 mux
s0_pin_encoder = 22
s1_pin_encoder = 4
s2_pin_encoder = 12
sel_pins_encoder = [s0_pin_encoder, s1_pin_encoder, s2_pin_encoder]
mux_output = 23 

#pin declarations for 1 to 8 mux
s0_pin_power = 19
s1_pin_power = 5
s2_pin_power = 26
sel_pins_power = [s0_pin_power,s1_pin_power,s2_pin_power]

#setup as inputs or outputs
GPIO.setup(step_pin_1,GPIO.OUT)  
GPIO.setup(direction_pin_1,GPIO.OUT)  
GPIO.setup(step_pin_2,GPIO.OUT)  
GPIO.setup(direction_pin_2,GPIO.OUT)  
GPIO.setup(PWM_pin,GPIO.OUT)
GPIO.setup(AIN1_pin,GPIO.OUT)  
GPIO.setup(AIN2_pin,GPIO.OUT)  

GPIO.setup(s0_pin_encoder,GPIO.OUT)
GPIO.setup(s1_pin_encoder,GPIO.OUT)  
GPIO.setup(s2_pin_encoder,GPIO.OUT) 
GPIO.setup(mux_output,GPIO.IN,pull_up_down = GPIO.PUD_DOWN)

GPIO.setup(s0_pin_power,GPIO.OUT)  
GPIO.setup(s1_pin_power,GPIO.OUT)  
GPIO.setup(s2_pin_power,GPIO.OUT)  

#GPIO pin initializations
GPIO.output(step_pin_1,GPIO.LOW)
GPIO.output(direction_pin_1,GPIO.LOW)
GPIO.output(step_pin_2,GPIO.LOW)
GPIO.output(direction_pin_2,GPIO.LOW)
GPIO.output(AIN2_pin,GPIO.LOW)
GPIO.output(AIN1_pin,GPIO.LOW) 
GPIO.output(s0_pin_encoder,GPIO.LOW)
GPIO.output(s1_pin_encoder,GPIO.LOW)
GPIO.output(s2_pin_encoder,GPIO.LOW) 
GPIO.output(s0_pin_power,GPIO.LOW)
GPIO.output(s1_pin_power,GPIO.LOW)
GPIO.output(s2_pin_power,GPIO.LOW)

#PWM variables
freq = 100
duty_cycle_stop = 0
duty_cycle_full = 50 

#create a PWM object on stepper motor step pins
#create a PWM object on stepper motor step pins
step_1_pwm = GPIO.PWM(step_pin_1, 95)	# left stepper
step_2_pwm = GPIO.PWM(step_pin_2, 95)	# right stepper

step_motor_pwm = [step_1_pwm,step_2_pwm]

step_1_pwm.start(duty_cycle_stop)
step_2_pwm.start(duty_cycle_stop)

#variable for the number of rows and columns in entire board
num_cols = 8
num_rows = 8

#create a PWM object on GPIO 16
pwm16 = GPIO.PWM(PWM_pin, 1000)
pwm16.start(duty_cycle_stop)
# ~ GPIO.output(PWM_pin, GPIO.LOW)
payload_pos = [0, 0]

left_offset = 9
right_offset = 3
up_offset = 5
down_offset = 6


# ---------------------------- END OF INIT ---------------------------- 

#pass through desired directions for both motors.  
#direction is an int (valid inputs are 0 for CW and 1 for CCW)
# num_steps is an int 
def step(direction, num_steps):
	if (direction[0] == 0): 
		GPIO.output(direction_pin_1,GPIO.LOW)
	else: 
		GPIO.output(direction_pin_1,GPIO.HIGH)
	if (direction[1] == 0): 
		GPIO.output(direction_pin_2,GPIO.LOW)
	else: 
		GPIO.output(direction_pin_2,GPIO.HIGH)
	move_stepper(num_steps)
	
# ~ #threading helper function for moving the stepper motors in sync
def set_stepper_step_output(step_pin, num_steps):
	for i in range(num_steps):
		GPIO.output(step_pin,GPIO.HIGH)
		time.sleep(0.001)
		GPIO.output(step_pin,GPIO.LOW)
		# ~ print(str(step_pin) + " is off")

#moves the stepper motor for a certain number of steps
def move_stepper(num_steps):
	all_stepper_motor_processes = []
	for i in range(2):
		stepper_motor_process = multiprocessing.Process(target = set_stepper_step_output_high(i))
		stepper_motor_process.start()
		# ~ print(str(i) + "started")
		all_stepper_motor_processes.append(stepper_motor_process)
	time.sleep(num_steps*0.05)
	j=0
	for process in all_stepper_motor_processes:
		process.terminate()
		set_stepper_step_output_low(j)
		# ~ print(str(j)+ "terminated")
		j+=1

#threading helper function for moving the stepper motors in sync
def set_stepper_step_output_high(step_pin):
	step_motor_pwm[step_pin].ChangeDutyCycle(duty_cycle_full)
	
#threading helper function for moving the stepper motors in sync
def set_stepper_step_output_low(step_pin):
	step_motor_pwm[step_pin].ChangeDutyCycle(duty_cycle_stop)


def pickup_motor(direction):
	# ~ print("pickup motor: " + str(direction))
	if direction == 1: #up
		GPIO.output(AIN1_pin,GPIO.HIGH)
		GPIO.output(AIN2_pin,GPIO.LOW)
		pwm16.ChangeDutyCycle(duty_cycle_full)
	if direction == 0: #down
		GPIO.output(AIN2_pin,GPIO.HIGH)
		GPIO.output(AIN1_pin,GPIO.LOW)
		pwm16.ChangeDutyCycle(duty_cycle_full)
	#stop
	time.sleep(0.032)
	pwm16.start(duty_cycle_stop)
	# ~ time.sleep(1)

def fine_tune(motor):
	print("start tune")
	if motor:
		pickup_motor(1)
	max_wiggle = 5
	counter = 0
	counter_weight = 1
	direction = right
	while(1):
		# ~ pickup_motor(1)
		step(direction, 1)
		check = read_tile(payload_pos)
		if check == 0:
			break
		if counter >= max_wiggle:
			max_wiggle += 2
			counter = 0
			counter_weight += 1
			if (direction == right):
				direction = up
			elif (direction == up):
				direction = left
			elif (direction == left):
				direction = down
			elif (direction == down):
				direction = right
		else:
			counter += 1

	if motor:
		pickup_motor(0)
	print("exit_tune")

			
def wait_for_board_match(old_board):
	current_board = current_board_state()
	same = 1
	while(same):
		state = compare_board_state(old_board, current_board)
		current_board = current_board_state()
		if (state == [[-1, -1], [-1, -1]]):
			same = 0
			print("board state returned")
		for curr_row in range(num_rows):
			concat_str = ""
			if (curr_row == 3 or curr_row == 4):
				for col in range(num_cols):
					concat_str += (str(current_board[7-curr_row][col]) + " ")
				concat_str += " =======> "
				for col in range(num_cols):
					concat_str += (str(old_board[7-curr_row][col]) + " ")
			else:
				for col in range(num_cols):
					concat_str += (str(current_board[7-curr_row][col]) + " ")
				concat_str += "          "
				for col in range(num_cols):
					concat_str += (str(old_board[7-curr_row][col]) + " ")
			print(concat_str)

pause_time = 6

# Moves the payload a certain number of tiles
def move_payload(target_x, target_y, tune):
	num_steps_increment = 1
	rel_pos_x = 0
	rel_pos_y = 0
	current_board = current_board_state()

	# ~ print("move payload x axis start")
	if (target_x > 0):
		step(right, pause_time)
	elif (target_x < 0):
		step(left, pause_time)	
	prev_x_sensor_state = 0
	while(rel_pos_x != target_x):
		# Needs to move right
		if (target_x > rel_pos_x):	
			step(right, num_steps_increment)
			if ((GPIO.input(encoder_x) == 0) and (prev_x_sensor_state == 1)): 
				rel_pos_x += 1 #update the coordinates when a magnet is passed
				payload_pos[0] += 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ fine_tune()
				prev_x_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		# ~ # Needs to move left
		elif (target_x < rel_pos_x):		
			step(left, num_steps_increment)
			if (GPIO.input(encoder_x) == 0 and (prev_x_sensor_state == 1)): 
				rel_pos_x -= 1 #update the coordinates when a magnet is passed
				payload_pos[0] -= 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ fine_tune()
				prev_x_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		if ((GPIO.input(encoder_x) == 1)):
			prev_x_sensor_state = 1
	if (target_x > 0):
		step(right, right_offset)
	elif (target_x < 0):	# right
		step(left, left_offset)

	# ~ print("move payload y axis start")
	if (target_y > 0):
		step(up, pause_time)
	elif (target_y < 0):
		step(down, pause_time)	
	prev_y_sensor_state = 0
	while(rel_pos_y != target_y):
		# Needs to move up
		if (target_y > rel_pos_y):
			step(up, num_steps_increment)
			if ((GPIO.input(encoder_y) == 0) and (prev_y_sensor_state == 1)): 
				rel_pos_y += 1 #update the coordinates when a magnet is passed
				payload_pos[1] += 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ fine_tune()
				prev_y_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		# Needs to move down
		elif (target_y < rel_pos_y): #Need to move right
			step(down, num_steps_increment)
			if (GPIO.input(encoder_y) == 0 and (prev_y_sensor_state == 1)): 
				rel_pos_y -= 1 #update the coordinates when a magnet is passed
				payload_pos[1] -= 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ fine_tune()
				prev_y_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		if ((GPIO.input(encoder_y) == 1)):
			prev_y_sensor_state = 1
	if (target_y < 0): #down
		step(down, down_offset)
	elif (target_y > 0):	 # up
		step(up, up_offset)	
	print("move payload done")

half_step_increment = 17 #set to value for half step
# all relative positioning
def move_piece(target_x, target_y, tune):
	num_steps_increment = 1
	# ~ pause_time = 7
	rel_pos_x = 0
	rel_pos_y = 0
	current_board = current_board_state()
	pickup_motor(1)
	# ~ print("move piece x axis start")
	step(up, half_step_increment)
	if (target_x > 0):
		step(right, pause_time)
	elif (target_x < 0):
		step(left, pause_time)	
	prev_x_sensor_state = 0
	while(rel_pos_x != target_x):
		# Needs to move right
		if (target_x > rel_pos_x):
			step(right, num_steps_increment)
			if ((GPIO.input(encoder_x) == 0) and (prev_x_sensor_state == 1)): 
				rel_pos_x += 1 #update the coordinates when a magnet is passed
				payload_pos[0] += 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ step(down, half_step_increment)
					# ~ fine_tune(False)				
					# ~ step(up, half_step_increment)
				prev_x_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		# Needs to move left
		elif (target_x < rel_pos_x):		
			step(left, num_steps_increment)
			if (GPIO.input(encoder_x) == 0 and (prev_x_sensor_state == 1)): 
				rel_pos_x -= 1 #update the coordinates when a magnet is passed
				payload_pos[0] -= 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ step(down, half_step_increment)
					# ~ fine_tune(False)
					# ~ step(up, half_step_increment)
				prev_x_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		if ((GPIO.input(encoder_x) == 1)):
			prev_x_sensor_state = 1
	if (target_x > 0):
		step(right, right_offset)
	elif (target_x < 0):	# right
		step(left, left_offset)
		
	# ~ print("move piece y axis start")
	step(right, half_step_increment)
	if (target_y > 0):
		step(up, pause_time)
	elif (target_y < 0):
		step(down, pause_time)	
		# Cornercase
		rel_pos_y += 1
		payload_pos[1] += 1
	prev_y_sensor_state = 0
	while(rel_pos_y != target_y):
		# Needs to move up
		if (target_y > rel_pos_y):
			step(up, num_steps_increment)
			if ((GPIO.input(encoder_y) == 0) and (prev_y_sensor_state == 1)): 
				rel_pos_y += 1 #update the coordinates when a magnet is passed
				payload_pos[1] += 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ step(left, half_step_increment)
					# ~ fine_tune(False)
					# ~ step(right, half_step_increment)
				prev_y_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		# Needs to move down
		elif (target_y < rel_pos_y): 
			step(down, num_steps_increment)
			if (GPIO.input(encoder_y) == 0 and (prev_y_sensor_state == 1)): 
				rel_pos_y -= 1 #update the coordinates when a magnet is passed
				payload_pos[1] -= 1
				target = current_board[payload_pos[0]][payload_pos[1]]
				if (target == 1 or tune == False):
					pass
				else:
					pass
					# ~ step(left, half_step_increment)
					# ~ fine_tune(False)
					# ~ step(right, half_step_increment)
				prev_y_sensor_state = 0
				# ~ print((rel_pos_x, rel_pos_y))
		if ((GPIO.input(encoder_y) == 1)):
			prev_y_sensor_state = 1
			
	if (target_y < 0): #down
		step(down, down_offset)
	elif (target_y > 0):	 # up
		step(up, up_offset)		
	step(left, half_step_increment)
	print("move piece done")
	pickup_motor(0)


def move_piece_to_side():
	old_payload_pos = payload_pos[0]
	pickup_motor(1)
	step(up, half_step_increment)
	step(right, pause_time)
	prev_x_sensor_state = 0
	while(not payload_pos[0] == 9):
		# Needs to move right
		step(right, 1)
		if ((GPIO.input(encoder_x) == 0) and (prev_x_sensor_state == 1)): 
			# ~ rel_pos_x += 1 #update the coordinates when a magnet is passed
			payload_pos[0] += 1
			prev_x_sensor_state = 0
		if ((GPIO.input(encoder_x) == 1)):
			prev_x_sensor_state = 1
	step(down, half_step_increment)
	pickup_motor(0)
	while(not (payload_pos[0] == old_payload_pos)):
		step(left, 1)
		if ((GPIO.input(encoder_x) == 0) and (prev_x_sensor_state == 1)): 
			# ~ rel_pos_x += 1 #update the coordinates when a magnet is passed
			payload_pos[0] -= 1
			prev_x_sensor_state = 0
		if ((GPIO.input(encoder_x) == 1)):
			prev_x_sensor_state = 1
	# ~ move_payload(old_payload_pos[0], old_payload_pos[1], False)
# ---------------------------- END OF MOTOR HELPER FUNCTIONS ----------------------------

# ---------------------------- CHESS BOARD STATE FUNCTIONS ----------------------------

#takes a string input. Input is the binary version of the input and the select pins we want to toggle (8 to 1 or 1 to 8)
def setup_select_pins(col_to_check, sel_pins_array):
	for i in range(3): #set up all of the select_pins on the mux using the col_to_check binary string
		select_setting = col_to_check[3-i-1] #number of sel pins - 1 - pin we want
		if (select_setting == "1"): #set corresponding GPIO pin HIGH or LOW
			GPIO.output(sel_pins_array[i], GPIO.HIGH)
		else:
			GPIO.output(sel_pins_array[i], GPIO.LOW)

#powers to the respective column via the 1 to 8 Mux. Input is an int
def power_col(sel_col):
	 col_to_power = str(bin(int(sel_col)-1)[2:]) #column we are currently checking as a binary number string
	 if (len(col_to_power) < 3):
		 col_to_power = '0' * (3 - len(col_to_power)) + col_to_power
	 # ~ print(col_to_power)
	 setup_select_pins(col_to_power, sel_pins_power)

#resets select bits on mux specified
def reset_sel_outputs(sel_pin_array):
	for i in range(3):
		GPIO.output(sel_pin_array[i], GPIO.LOW)

def read_tile(coords):
	# ~ print(coords)
	power_col(coords[1] + 1)
	time.sleep(0.01)
	row_to_check_encoder = str(bin(coords[0]))[2:]
	if (len(row_to_check_encoder) < 3): #ensures column bin string is 3 digits long
		row_to_check_encoder = '0' * (3 - len(row_to_check_encoder)) + row_to_check_encoder
	setup_select_pins(row_to_check_encoder, sel_pins_encoder) #sets up the select pin
	return GPIO.input(mux_output)

#scan the board using the 8 to 1 mux and return the state of the board. print it in an 8x8 array in 1s and 0s
#returns the current board state
def current_board_state():
	#initialize current board state variable
	curr_board_array = [[0 for i in range(num_cols)] for j in range(num_rows)]
	#go through each row
	for j in range(num_cols):
		# ~ print("checking col: " + str(j+1))
		power_col(j+1)
		time.sleep(0.1)
		#in each column, check the row to see if there is a piece detected by the hall effect sensor there
		for i in range(num_rows):
			row_to_check_encoder = str(bin(i))[2:] #column we are currently checking as a binary number string
			if (len(row_to_check_encoder) < 3): #ensures column bin string is 3 digits long
				row_to_check_encoder = '0' * (3 - len(row_to_check_encoder)) + row_to_check_encoder
			# ~ print(row_to_check_encoder)
			# ~ time.sleep(1)
			setup_select_pins(row_to_check_encoder, sel_pins_encoder) #sets up the select pin
			if (GPIO.input(mux_output) == 0): #hall effect sensors pull low when there is a magnet nearby
				curr_board_array[i][j] = 1 #write a 1 to indicate there is a piece 
		# ~ print(curr_board_array[i])
		reset_sel_outputs(sel_pins_encoder)
		# ~ time.sleep(10)
	# ~ #print the state of the board 
	# ~ for curr_row in range(num_rows):
		# ~ print(curr_board_array[7-curr_row])
	# ~ print("------------------------------------")
	# ~ time.sleep(0.5)
	return curr_board_array
	

#compares the current board state with the previous board state by going row by row and seeing if there are any changes
#returns the initial and final coordinates of the piece that was moved as an array
def compare_board_state(prev_board_array, curr_board_array):
	final_position = [-1, -1]
	initial_position = [-1, -1]
	for row_comp in range(num_rows): #goes through each of the rows
		for col_comp in range(num_cols): #goes through each of the columns
			if prev_board_array[row_comp][col_comp] != curr_board_array[row_comp][col_comp]: #checks for changes
				if (curr_board_array[row_comp][col_comp] == 1): #piece was moved here
					final_position = [row_comp, col_comp]
				else: #piece was moved from here
					initial_position = [row_comp, col_comp] 
	piece_change_coords = [initial_position, final_position]
	return piece_change_coords

#takes an array was each element in the form [x,y] and translates it to a string 
def coord_to_uci(coord_array):
	letter = chr(ord('a') + coord_array[0])
	final_string = letter + str(coord_array[1] + 1)
	return final_string

#used to check if a piece is lifted and then placed onto the board
def sum_pieces_on_board(board):
	num_pieces = 0 
	for row in range(num_rows):
		for col in range(num_cols):
			num_pieces += board[row][col]
	return num_pieces
	
		
def init_board():
	board_str = [["r", "n", "b", "q", "k", "b", "n", "r"], ["p", "p", "p", "p", "p", "p", "p", "p"], [".", ".", ".", ".", ".", ".", ".", "."], [".", ".", ".", ".", ".", ".", ".", "."], [".", ".", ".", ".", ".", ".", ".", "."], [".", ".", ".", ".", ".", ".", ".", "."], ["P", "P", "P", "P", "P", "P", "P", "P"], ["R", "N", "B", "Q", "K", "B", "N", "R"]]
	# ~ board_str[2:6] = [".", ".", ".", ".", ".", ".", ".", "."]
	return board_str

def convert_bin_to_board(old_bin_board, old_str_board, new_bin_board):
	new_str_board = old_str_board
	orig_coords, final_coords = compare_board_state(old_bin_board, new_bin_board)
	new_str_board[final_coords[0]][final_coords[1]] = old_str_board[orig_coords[0]][orig_coords[0]]
	new_str_board[orig_coords[0]][orig_coords[1]] = "."
	return new_str_board
	# ~ if start:

def convert_str_to_uci(str_board):
	uci_board = ""
	for i in range(len(str_board)):
		for j in range(len(str_board[0])):
			uci_board += str_board[i][j] + " "
	return uci_board

def fen_to_str(fen_str):
	split_string = fen_str.split("/")
	board = []
	for string in split_string:
		temp_row = []
		string = string[0:8]
		for item in string:
			if item.isnumeric():
				for i in range(int(item)):
					temp_row.append(".")
			else:
				temp_row.append(item)
		board.append(temp_row)
			
	# ~ print(board)
	return board
		
	
def wait_for_board_match(old_board):
	same = 1
	while(same):
		current_board = current_board_state()
		state = compare_board_state(old_board, current_board)
		if (state == [[-1, -1], [-1, -1]]):
			same = 0
			print("board state returned")
			return()
		for curr_row in range(num_rows):
			concat_str = ""
			if (curr_row == 3 or curr_row == 4):
				for col in range(num_cols):
					concat_str += (str(current_board[curr_row][col]) + " ")
				concat_str += " =======> "
				for col in range(num_cols):
					concat_str += (str(old_board[curr_row][col]) + " ")
			else:
				for col in range(num_cols):
					concat_str += (str(current_board[curr_row][col]) + " ")
				concat_str += "          "
				for col in range(num_cols):
					concat_str += (str(old_board[curr_row][col]) + " ")
			print(concat_str)
		print("-------------")

# ---------------------------- END OF CHESS BOARD STATE FUNCTIONS ----------------------------

# ---------------------------- GAME STATE FUNCTIONS ----------------------------

def print_board(board):
	# ~ curr_board_array = np.rot90(board)
	for curr_row in range(len(board)):
		print(board[curr_row])
	print("------------------------------------")
	

all_ones = [1, 1, 1, 1, 1, 1, 1, 1]
all_zeros = [0, 0, 0, 0, 0, 0, 0, 0]	
init_board_array = [all_ones, all_ones, all_zeros, all_zeros, all_zeros, all_zeros, all_ones, all_ones]
# ---------------------------- MAIN ---------------------------- 
try:
	#game in session
	board = chess.Board()
	fen_board = board.fen()
	engine = chess.engine.SimpleEngine.popen_uci("/home/pi/FinalProject/Stockfish/src/stockfish")
	print("Reset to 0")
	init_x = int(input("Number to move X: "))
	init_y = int(input("Number to move Y: "))
		
	move_payload(init_x, init_y, False)

	payload_pos = [0, 0]
	fine_tune(True)
	init = 0
	# ~ while(not init):
	# ~ curr_board_array = current_board_state()
	# ~ print_board(curr_board_array)
		# ~ num_pieces = sum_pieces_on_board(curr_board_array)	
		# ~ if (num_pieces == 32):
			# ~ init = 1
	
	while not board.is_game_over():
		# Player's turn
		print(board)
		if board.turn == chess.WHITE:
			prev_board_array = current_board_state()
			found_move = 0
			while(not found_move):
				temp_1_board_state = current_board_state()
				init_coords, final_coords = compare_board_state(prev_board_array, temp_1_board_state)
				if (not final_coords == [-1, -1]):
					found_move = 1
					initial_coord_string = coord_to_uci(init_coords)
					final_coord_string = coord_to_uci(final_coords)
					move_uci = initial_coord_string + final_coord_string
			# ~ move_uci = input("Enter move:") #change this later on to poll the physical board for position of pieces
			try:
				move = chess.Move.from_uci(move_uci)
				if move in board.legal_moves:
					board.push(move)
				else:
					print("Invalid. Try again.")
			except ValueError:
				print("Invalid move format. Try again.")
					
		else:
			result = engine.play(board, chess.engine.Limit(time=0.1))
			print("CPU move: ", result.move)
			CPU_move = result.move.uci() #gets the move as a string
			if board.is_capture(result.move):
				capture = True
			else:
				capture = False
			board.push(result.move)
			end_coords = [ord(CPU_move[2]) - 96 - 1, int(CPU_move[3]) - 1] #splices move string and converts char to int for x and y end coordinates
			piece_coords = [ord(CPU_move[0]) - 96 - 1,int(CPU_move[1]) - 1] #splices move string and converts char to int for x and y start coordinates
			if capture:
				print("Capture")
				move_payload(end_coords[0] - payload_pos[0], end_coords[1] - payload_pos[1], True)
				fine_tune(True)
				move_piece_to_side()
				# ~ print("starting at: " + str(x_curr_coord) + "," + str(y_curr_coord))
				# ~ print("picking piece at: " + str(piece_coords[0]) + ", " + str(piece_coords[1]))
				# ~ print("dropping the piece off at: " + str(end_coords[0]) + ", " + str(end_coords[1]))
			move_payload(piece_coords[0] - payload_pos[0], piece_coords[1] - payload_pos[1], True)
			payload_pos[0] = piece_coords[0]
			payload_pos[1] = piece_coords[1]
			fine_tune(True)
			move_piece(end_coords[0] - payload_pos[0], end_coords[1] - payload_pos[1], True)
			payload_pos[0] = end_coords[0]
			payload_pos[1] = end_coords[1]
			fine_tune(True)

except KeyboardInterrupt:
	pass
print("game over")
GPIO.cleanup()
quit()


