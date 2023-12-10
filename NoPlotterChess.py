#main code for the chess project. To run in the terminal, use the command:
#sudo -E python [filename]

# Modules
import time 
import RPi.GPIO as GPIO
import chess
import chess.engine
from threading import Thread
import multiprocessing
import numpy as np

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

GPIO.setup(s0_pin_encoder,GPIO.OUT)
GPIO.setup(s1_pin_encoder,GPIO.OUT)  
GPIO.setup(s2_pin_encoder,GPIO.OUT) 
GPIO.setup(mux_output,GPIO.IN,pull_up_down = GPIO.PUD_DOWN)

GPIO.setup(s0_pin_power,GPIO.OUT)  
GPIO.setup(s1_pin_power,GPIO.OUT)  
GPIO.setup(s2_pin_power,GPIO.OUT)  

GPIO.output(s0_pin_encoder,GPIO.LOW)
GPIO.output(s1_pin_encoder,GPIO.LOW)
GPIO.output(s2_pin_encoder,GPIO.LOW) 
GPIO.output(s0_pin_power,GPIO.LOW)
GPIO.output(s1_pin_power,GPIO.LOW)
GPIO.output(s2_pin_power,GPIO.LOW)

num_rows = 8
num_cols = 8

# ---------------------------- END OF INIT ---------------------------- 


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

#scan the board using the 8 to 1 mux and return the state of the board. print it in an 8x8 array in 1s and 0s
#returns the current board state
def current_board_state():
	#initialize current board state variable
	curr_board_array = [[0 for i in range(num_cols)] for j in range(num_rows)]
	#go through each row
	for j in range(num_cols):
		# ~ print("checking col: " + str(j+1))
		power_col(j+1)
		time.sleep(0.05)
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
	curr_board_array = np.rot90(curr_board_array).tolist()
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
	letter = chr(ord('a') + (coord_array[1]))
	final_string = letter + str(8-coord_array[0])
	return final_string

def uci_to_coords(uci_string):
	x_index = int(ord('a')-ord(uci_string[0]))
	y_index = int(uci_string[1]) - 1
	return x_index, y_index
	
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
	init = 0
	while(not init):
		curr_board_array = current_board_state()
		print_board(curr_board_array)
		num_pieces = sum_pieces_on_board(curr_board_array)	
		if (curr_board_array == init_board_array):
			init = 1
	sim_board = fen_to_str(fen_board)
	
	while not board.is_game_over():
		# Player's turn
		# ~ print_board(phys_board)
		if board.turn == chess.WHITE:
			valid_move = 0
			print("Your move (White)")
			while(not valid_move):
				prev_board_array = current_board_state()
				print_board(prev_board_array)
				print(board)
				found_move = 0
				# wait for a complete move
				while(not found_move):
					temp_1_board_state = current_board_state()
					init_coords, final_coords = compare_board_state(prev_board_array, temp_1_board_state)
					if (not init_coords == [-1, -1]):
						# the piece picked up is the player's piece
						if (sim_board[init_coords[0]][init_coords[1]].isupper()):
							if (not final_coords == [-1, -1]):
								found_move = 1
								initial_coord_string = coord_to_uci(init_coords)
								final_coord_string = coord_to_uci(final_coords)
								uci_input_string = initial_coord_string + final_coord_string
						else:
							print("Capture attempted")
							found_capture = 0
							while(not found_capture):
								temp_2_board_state = current_board_state()
								init_coords_2, final_coords_2 = compare_board_state(temp_1_board_state, temp_2_board_state)
								if (not init_coords_2 == [-1, -1] and not final_coords_2 == [-1, -1]):
									if (not final_coords_2 == init_coords):
										uci_string = coord_to_uci(init_coords_2) + coord_to_uci(final_coords_2)
										print("Capture {} Invalid. Please return board to original state".format(uci_string))
										wait_for_board_match(prev_board_array)
										found_capture = 0
									else:
										print("Capture found")
										found_capture = 1
										found_move = 1
										initial_coord_string = coord_to_uci(init_coords_2)
										final_coord_string = coord_to_uci(final_coords_2)
										uci_input_string = initial_coord_string + final_coord_string
								# ~ print("capture")

						

					#move_uci = user_turn() #returns a string that the chess engine can take
				print("move: " + uci_input_string)
				try:
					move = chess.Move.from_uci(uci_input_string)
					if move in board.legal_moves:
						valid_move = 1
						board.push(move)
						sim_board = fen_to_str(board.fen())
					else:
						print("Move {} Invalid. Please return board to original state".format(uci_input_string))
						wait_for_board_match(prev_board_array)
						print("Your move (White)")
						print(board)
				except ValueError:
					print("Bug")
					
		else:
			result = engine.play(board, chess.engine.Limit(time=0.1))
			print("CPU move: ", result.move)
			CPU_move = result.move.uci() #gets the move as a string
			end_coords = [ord(CPU_move[2]) - 96 - 1, int(CPU_move[3]) - 1] #splices move string and converts char to int for x and y end coordinates
			piece_coords = [ord(CPU_move[0]) - 96 - 1,int(CPU_move[1]) - 1] #splices move string and converts char to int for x and y start coordinates
			shifted_end_coords = [end_coords[0], 7-end_coords[1]]
			shifted_piece_coords = [piece_coords[0], 7-piece_coords[1]]
			if board.is_capture(result.move):
				capture = True
			else:
				capture = False
			prev_board_array = current_board_state()
			board.push(result.move)
			print_board(prev_board_array)
			ready = 0
			# ~ print(shifted_piece_coords, shifted_end_coords)
			print(board)
			if capture:
				print("{} at {} captured {} at {}".format(sim_board[7-end_coords[1]][end_coords[0]], CPU_move[0:2], sim_board[7-piece_coords[1]][piece_coords[0]], CPU_move[2:4]))
				while (not ready):
					curr_board_array = current_board_state()
					orig_coords, final_coords = compare_board_state(prev_board_array, curr_board_array) #change the change
					change_coord_str = coord_to_uci(piece_change_coords[0]) + coord_to_uci(piece_change_coords[1])
					orig_coords = [orig_coords[0], 7-orig_coords[1]]
					# ~ print(orig_coords, final_coords)
					if (end_coords == orig_coords):
						print("Capture detected")
						while (not ready):
							new_board_array = current_board_state()
							piece_change_coords = compare_board_state(curr_board_array, new_board_array) #change the change
							change_coord_str = coord_to_uci(piece_change_coords[0]) + coord_to_uci(piece_change_coords[1])
							# ~ print(change_coord_str)
							if (change_coord_str == CPU_move):
								ready = 1
					elif (not final_coords == [-1, -1]):
						print("Wrong capture") 
						wait_for_board_match(prev_board_array)

			else:
				while (not ready):
					curr_board_array = current_board_state()
					piece_change_coords = compare_board_state(prev_board_array, curr_board_array) #change the change
					change_coord_str = coord_to_uci(piece_change_coords[0]) + coord_to_uci(piece_change_coords[1])
					if (not piece_change_coords[0] == [-1, -1]) and (not piece_change_coords[1] == [-1, -1]):  
						if (change_coord_str == CPU_move):
							ready = 1
							print("Move complete")
						else:
							print("Move {} does not match. Please return board to original state".format(change_coord_str))
							wait_for_board_match(prev_board_array)
							print("CPU move: ", result.move)
							print(board)

			sim_board = fen_to_str(board.fen())
except KeyboardInterrupt:
	pass
print("game over")
GPIO.cleanup()
quit()

