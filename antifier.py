#based on T1932 protocol
import usb.core
import time
import ant, trainer
import sys
import binascii
import struct
import platform, glob
import os
import threading
import Tkinter
import pickle
#from pynput import keyboard
from Tkinter import *
from tkMessageBox import *

from datetime import datetime
import argparse

#global KeyPoller

#from classes import KeyPoller 




if os.name == 'posix':
  import serial

#powerfactor = 1
#debug = False
#simulatetrainer = False
parser = argparse.ArgumentParser(description='Program to broadcast data from USB Tacx trainer, and to receive resistance data for the trainer')
parser.add_argument('-d','--debug', help='Show debugging data', required=False, action='store_true')
parser.add_argument('-s','--simulate-trainer', help='Simulated trainer to test ANT+ connectivity', required=False, action='store_true')
parser.add_argument('-p','--power-factor', help='Adjust broadcasted power data by multiplying measured power by this factor', required=False, default="1")
parser.add_argument('-l','--headless', help='Run headless, requires -c', required=False, action='store_true')
parser.add_argument('-c','--power-curve', help='Choose power curve file', required=False)
args = parser.parse_args()
powerfactor = args.power_factor
debug = args.debug
simulatetrainer = args.simulate_trainer
headless = args.headless

switch = True
runoff_loop_running = False



filename = "Head_unit_setup.txt"

#speed, pedecho, heart_rate, force_index, cadence = 30, 0, 120, 5, 70
current_speed, current_heart_rate, current_cadence = 0, 100, 0


try:
  f = open(filename, 'r')
except IOError:
  f= open(filename,"w+")
  f.write("This file contains information regarding Head Unit buttons and Zwift keyboard shortcuts mapping \r\n")
  f.write("PGUP \r\n")
  f.write("PGDOWN \r\n")
  f.write("0 \r\n")
  f.write("SB \r\n")
  f.close()

f.close()

f = open(filename, 'r')
fileAsList = f.readlines()

UP = fileAsList[1] 
DOWN = fileAsList[2] 
ENTER = fileAsList[3]
CANCEL = fileAsList[4]

f.close()



global isWindows

isWindows = False
try:
    from win32api import STD_INPUT_HANDLE
    from win32console import GetStdHandle, KEY_EVENT, ENABLE_ECHO_INPUT, ENABLE_LINE_INPUT, ENABLE_PROCESSED_INPUT
    isWindows = True
except ImportError as e:
    import sys
    import select
    import termios


class KeyPoller:
    def __enter__(self):
        global isWindows
        if isWindows:
            self.readHandle = GetStdHandle(STD_INPUT_HANDLE)
            self.readHandle.SetConsoleMode(ENABLE_LINE_INPUT|ENABLE_ECHO_INPUT|ENABLE_PROCESSED_INPUT)

            self.curEventLength = 0
            self.curKeysLength = 0

            self.capturedChars = []
        else:
            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

        return self

    def __exit__(self, type, value, traceback):
        if isWindows:
            pass
        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

    def poll(self):
        if isWindows:
            if not len(self.capturedChars) == 0:
                return self.capturedChars.pop(0)

            eventsPeek = self.readHandle.PeekConsoleInput(10000)

            if len(eventsPeek) == 0:
                return None

            if not len(eventsPeek) == self.curEventLength:
                for curEvent in eventsPeek[self.curEventLength:]:
                    if curEvent.EventType == KEY_EVENT:
                        if ord(curEvent.Char) == 0 or not curEvent.KeyDown:
                            pass
                        else:
                            curChar = str(curEvent.Char)
                            self.capturedChars.append(curChar)
                self.curEventLength = len(eventsPeek)

            if not len(self.capturedChars) == 0:
                return self.capturedChars.pop(0)
            else:
                return None
        else:
            dr,dw,de = select.select([sys.stdin], [], [], 0)
            if not dr == []:
                return sys.stdin.read(1)
            return None


class PowerFactor_Window:
  def __init__(self, master):
    self.master = master
    self.frame = Tkinter.Frame(self.master)

    ###Setup GUI buttons and labels for entering power factor###

    self.buttonPwrFact = Tkinter.Button(self.frame,height=1, width=20,text=u"Set power factor",command=self.serPwrFactorbutton)
    self.buttonPwrFact.grid(column=0,row=0)

    self.PwrFactVariable = Tkinter.StringVar()
    self.entry = Tkinter.Entry(self.frame,textvariable=self.PwrFactVariable)
    self.entry.grid(column=0,row=1,sticky='EW')

    self.frame.pack()


  def serPwrFactorbutton(self):
    global powerfactor
    powerfactor = self.PwrFactVariable.get() 
    self.master.destroy()
   
class HeadUnit_Window:
  def __init__(self, master):
    self.master = master
    self.frame = Tkinter.Frame(self.master)

    ###Setup GUI buttons and labels###

    label = Tkinter.Label(self.frame,height=1, width=10,text="UP button")
    label.grid(column=0,row=0,sticky='EW')

    self.UPVariable = Tkinter.StringVar()
    self.entry = Tkinter.Entry(self.frame,textvariable=self.UPVariable)
    self.entry.grid(column=1,row=0,sticky='EW')
    self.UPVariable.set(UP)


    label = Tkinter.Label(self.frame,height=1, width=10,text="DOWN button")
    label.grid(column=0,row=1,sticky='EW')

    self.DOWNVariable = Tkinter.StringVar()
    self.entry = Tkinter.Entry(self.frame,textvariable=self.DOWNVariable)
    self.entry.grid(column=1,row=1,sticky='EW')
    self.DOWNVariable.set(DOWN)


    label = Tkinter.Label(self.frame,height=1, width=10,text="ENTER button")
    label.grid(column=0,row=2,sticky='EW')

    self.ENTERVariable = Tkinter.StringVar()
    self.entry = Tkinter.Entry(self.frame,textvariable=self.ENTERVariable)
    self.entry.grid(column=1,row=2,sticky='EW')
    self.ENTERVariable.set(ENTER)


    label = Tkinter.Label(self.frame,height=1, width=10,text="CANCEL button")
    label.grid(column=0,row=3,sticky='EW')

    self.CANCELVariable = Tkinter.StringVar()
    self.entry = Tkinter.Entry(self.frame,textvariable=self.CANCELVariable)
    self.entry.grid(column=1,row=3,sticky='EW')
    self.CANCELVariable.set(CANCEL)


    self.buttonHeadUnit = Tkinter.Button(self.frame,height=1, width=20,text=u"Update Head Unit",command=self.setHEADUNITbutton)
    self.buttonHeadUnit.grid(column=0,row=4)

    self.buttonNeedHelp = Tkinter.Button(self.frame,height=1, width=20,text=u"Need Help?",command=self.NEEDHELPbutton)
    self.buttonNeedHelp.grid(column=1,row=4)

    self.frame.pack()



  def setHEADUNITbutton(self):
    global UP,DOWN,ENTER,CANCEL
    
    UP = self.UPVariable.get()
    DOWN = self.DOWNVariable.get()
    ENTER = self.ENTERVariable.get()
    CANCEL = self.CANCELVariable.get()

    f = open(filename, 'w+')
    f.write("This file contains information regarding Head Unit buttons and Zwift keyboard shortcuts mapping \r\n")
    f.write(UP + '\n')
    f.write(DOWN + '\n')
    f.write(ENTER + '\n')
    f.write(CANCEL + '\n')
    f.close()

    self.master.destroy()

  def NEEDHELPbutton(self):
    os.startfile('Zwift_shortcuts.txt')


        
class Window(Frame):
  def __init__(self, master=None):
    if not headless:
      Frame.__init__(self,master)
      self.master = master
      self.init_window()

  def settrainer(self, n):
    global power_curve, user_defaults
    user_defaults['power_curve'] = n
    power_curve = n
    if n == "power_calc_factors_imagic.txt":
      self.PowerCurveVariable.set("I-Magic")
    elif n == "power_calc_factors_fortius.txt":
      self.PowerCurveVariable.set("Fortius")
    elif n == "power_calc_factors_custom.txt":
      self.PowerCurveVariable.set("Custom")
      
  
  def init_window(self):
    global user_defaults
    self.grid()

    ###Setup menu content###

    self.master.title("Antifier v0.9")
    self.master.option_add('*tearOff', False)

    # allowing the widget to take the full space of the root window
    self.pack(fill=BOTH, expand=1)

    # creating a menu instance
    menu = Menu(self.master)
    self.master.config(menu=menu)

    # create the Setup object)
    Setup = Menu(menu)

    # add commands to the Setup option
    Setup.add_command(label="Head Unit", command=self.HeadUnit_window)

    subSetup = Menu(Setup)
    subSetup.add_command(label='iMagic', command=lambda p="power_calc_factors_imagic.txt": self.settrainer(p))
    subSetup.add_command(label='Fortius', command=lambda p="power_calc_factors_fortius.txt": self.settrainer(p))   
    subSetup.add_command(label='Custom Curve', command=lambda p="power_calc_factors_custom.txt": self.settrainer(p))
    
    
    Setup.add_cascade(label='Power Curve', menu=subSetup)
    
    Setup.add_separator()
    Setup.add_command(label="Exit", command=self.EXITbutton)

    #added "Setup" to our menu
    menu.add_cascade(label="Setup", menu=Setup)


    # create the Options object)
    Options = Menu(menu)

    # add commands to the Options option
    Options.add_command(label="Debug", command=self.DebugButton)
    Options.add_command(label="Simulate Trainer", command=self.Simulatebutton)
    Options.add_command(label="Power Factor", command=self.PowerFactor_Window)

    #added "Options" to our menu
    menu.add_cascade(label="Options", menu=Options)



    # create the Help object
    Help = Menu(menu)

    # adds a command to the Help option.
    Help.add_command(label="Readme", command=self.Readme)
    Help.add_command(label="Zwift shortcuts", command=self.Zwift_shortcuts)

    #added "Help" to our menu
    menu.add_cascade(label="Help", menu=Help)



    ###Setup GUI buttons and labels###

    self.FindHWbutton = Tkinter.Button(self,height=1, width=15,text=u"1. Locate HW",command=self.ScanForHW)
    self.FindHWbutton.grid(column=0,row=0)


    label = Tkinter.Label(self,height=1, width=10,text="Head Unit")
    label.grid(column=0,row=1,sticky='EW')
    self.trainerVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.trainerVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=1,columnspan=2,sticky='EW')
    
    label = Tkinter.Label(self,height=1, width=10,text="Power curve")
    label.grid(column=0,row=2,sticky='EW')
    self.PowerCurveVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.PowerCurveVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=2,columnspan=2,sticky='EW')
    if 'power_curve' in user_defaults:
      self.settrainer(user_defaults['power_curve'])



    label = Tkinter.Label(self,height=1, width=10,text="ANT+")
    label.grid(column=0,row=3,sticky='EW')
    self.ANTVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.ANTVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=3,columnspan=2,sticky='EW')


    label = Tkinter.Label(self,text="Power factor")
    label.grid(column=0,row=4,sticky='EW')
    self.PowerFactorVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.PowerFactorVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=4,columnspan=2,sticky='EW')

    self.RunoffButton = Tkinter.Button(self,height=1, width=15,text=u"2. Perform Runoff",command=self.Runoff)
    self.RunoffButton.grid(column=0,row=5)
    self.RunoffButton.config(state="disabled")
    self.runoffVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.runoffVariable,anchor="w",fg="black",bg="grey", width=40)
    label.grid(column=1,row=5,columnspan=2,sticky='EW')

    self.StartAPPbutton = Tkinter.Button(self,height=1, width=15,text=u"3. Start script",command=self.Start)
    self.StartAPPbutton.grid(column=0,row=6)
    self.StartAPPbutton.config(state="disabled")

    self.StopAPPbutton = Tkinter.Button(self,height=1, width=15,text=u"Stop script",command=self.Stop, state="disabled")
    self.StopAPPbutton.grid(column=1,row=6)
    

    label = Tkinter.Label(self,text="Speed")
    label.grid(column=0,row=7,sticky='EW')

    self.SpeedVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.SpeedVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=7,columnspan=2,sticky='EW')
    self.SpeedVariable.set(u"0")


    label = Tkinter.Label(self,text="Heartrate")
    label.grid(column=0,row=8,sticky='EW')
    self.HeartrateVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.HeartrateVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=8,columnspan=2,sticky='EW')
    self.HeartrateVariable.set(u"0")

    label = Tkinter.Label(self,text="Cadence")
    label.grid(column=0,row=9,sticky='EW')

    self.CadenceVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.CadenceVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=9,columnspan=2,sticky='EW')
    self.CadenceVariable.set(u"0")


    label = Tkinter.Label(self,text="Power")
    label.grid(column=0,row=10,sticky='EW')
    self.PowerVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.PowerVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=10,columnspan=2,sticky='EW')
    self.PowerVariable.set(u"0")

    label = Tkinter.Label(self,text="Slope")
    label.grid(column=0,row=11,sticky='EW')
    self.SlopeVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.SlopeVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=11,columnspan=2,sticky='EW')
    
    label = Tkinter.Label(self,text="Target Power")
    label.grid(column=0,row=12,sticky='EW')
    self.TargetPowerVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.TargetPowerVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=12,columnspan=2,sticky='EW')
    
    label = Tkinter.Label(self,text="Resistance Level")
    label.grid(column=0,row=13,sticky='EW')
    self.ResistanceLevelVariable = Tkinter.StringVar()
    label = Tkinter.Label(self,textvariable=self.ResistanceLevelVariable,anchor="w",fg="black",bg="grey")
    label.grid(column=1,row=13,columnspan=2,sticky='EW')
    self.ResistanceLevelVariable.set(u"0")
    
    



  def PowerFactor_Window(self):
    self.PowerFactor_Window = Tkinter.Toplevel(self.master)
    self.app = PowerFactor_Window(self.PowerFactor_Window)

  def HeadUnit_window(self):
    self.HeadUnitWindow = Tkinter.Toplevel(self.master)
    self.app = HeadUnit_Window(self.HeadUnitWindow)

    
  def Runoff(self):
    global runoff_loop_running
    def run():
      global dev_trainer, runoff_loop_running
      rolldown = False
      rolldown_time = 0
      speed = 0
      #self.InstructionsVariable.set('''
  #CALIBRATION TIPS: 
  #1. Tyre pressure 100psi (unloaded and cold) aim for 7.2s rolloff
  #2. Warm up for 2 mins, then cycle 30kph-40kph for 30s 
  #3. Speed up to above 40kph then stop pedalling and freewheel
  #4. Rolldown timer will start automatically when you hit 40kph, so stop pedalling quickly!
  #''')
      
      while runoff_loop_running:#loop every 100ms
        last_measured_time = time.time() * 1000
        #receive data from trainer
        speed, pedecho, heart_rate, force_index, cadence = trainer.receive(dev_trainer) #get data from device
        self.SpeedVariable.set(speed)
        if speed == "Not found":
          self.TrainerStatusVariable.set("Check trainer is powered on")
        
        #send data to trainer
        resistance_level = 6
        trainer.send(dev_trainer, resistance_level, pedecho)
        
        if speed > 40:#speed above 40, start rolldown
          self.runoffVariable.set("Rolldown timer started - STOP PEDALLING!")
          rolldown = True
        
        if speed <=40 and rolldown:#rolldown timer starts when dips below 40
          if rolldown_time == 0:
            rolldown_time = time.time()#set initial rolldown time
          self.runoffVariable.set("Rolldown timer started - STOP PEDALLING! %s " % ( round((time.time() - rolldown_time),1) ) )
          
        if speed < 0.1 and rolldown:#wheel stopped
          runoff_loop_running = False#break loop
          self.runoffVariable.set("Rolldown time = %s seconds (aim 7s)" % round((time.time() - rolldown_time),1))

        time_to_process_loop = time.time() * 1000 - last_measured_time
        sleep_time = 0.1 - (time_to_process_loop)/1000
        if sleep_time < 0: sleep_time = 0
        time.sleep(sleep_time)
        
      self.RunoffButton.config(text="2. Perform Runoff")#reset runoff button
      self.StartAPPbutton.config(state="normal")
    
    if self.RunoffButton.cget('text')=="2. Perform Runoff":#start runoff
      self.runoffVariable.set('Cycle to above 40kph then stop')
      self.RunoffButton.config(text="2. Stop Runoff")
      self.StartAPPbutton.config(state="disabled")
      runoff_loop_running = True#loop switch
      t1 = threading.Thread(target=run)
      t1.start()
    else:#stop loop
      runoff_loop_running = False
      self.runoffVariable.set('Stopped')
      self.RunoffButton.config(text="2. Perform Runoff")
      self.StartAPPbutton.config(state="normal")
    
  def Readme(self):
    os.startfile('README.txt')

  def Zwift_shortcuts(self):
    os.startfile('Zwift_shortcuts.txt')

  def EXITbutton(self):
    self.destroy()
    exit()
    
  def DebugButton(self):
    global debug
    if debug == False:
      debug = True
    else:
      debug = False
 
  def Simulatebutton(self):
    global simulatetrainer
    simulatetrainer = True

  def Stop(self):
    global switch  
    switch = False  
    self.StartAPPbutton.config(state="normal")
    self.StopAPPbutton.config(state="disabled")


  def ScanForHW(self):
    global dev_trainer, dev_ant, simulatetrainer
    #get ant stick
    if debug:print "get ant stick"
    if not dev_ant:
      dev_ant, msg = ant.get_ant(debug)
      if not dev_ant:
        if not headless: self.ANTVariable.set(msg)
        return False
    if not headless: self.ANTVariable.set(msg)


    if not headless: self.PowerFactorVariable.set(powerfactor)
    if debug:print "get trainer"
    #find trainer model for Windows and Linux
    if not dev_trainer:
      #find trainer
      if simulatetrainer:
        if not headless: self.trainerVariable.set(u"Simulated Trainer")
        else: print "Simulated Trainer"
      else:
        dev_trainer = trainer.get_trainer()
        if not dev_trainer:
          if not headless: self.trainerVariable.set("Trainer not detected")
          else: print "Trainer not detected"
          return False
        else:
          if not headless: self.trainerVariable.set("Trainer detected")
          else: print "Trainer detected"
          trainer.initialise_trainer(dev_trainer)#initialise trainer
    
    if not headless: 
      self.StartAPPbutton.config(state="normal")
      if not simulatetrainer:
        self.RunoffButton.config(state="normal")
      self.FindHWbutton.config(state="disabled")
      
    return True

  def Start(self):
    
    def poller():
      global current_speed, current_cadence, current_heart_rate, KeyPoller
      with KeyPoller() as keyPoller:
        print ('poller thread started')
        while True:
          c = keyPoller.poll()
          if not c is None:
            if c == "q":
              print "Increasing speed"
              current_speed = current_speed + 1
            if c == "a":
              print "Decreasing speed"
              current_speed = current_speed - 1
            if c == "w":
              print "Increasing cadence"
              current_cadence = current_cadence + 1
            if c == "s":
              print "Decreasing cadence"
              current_cadence = current_cadence - 1
            if c == "e":
              print "Increasing HR"
              current_heart_rate = current_heart_rate + 1
            if c == "d":
              print "Decreasing HR"
              current_heart_rate = current_heart_rate - 1

    def run():
      global dev_ant, dev_trainer, simulatetrainer, switch, power_curve, current_speed, current_cadence, current_heartrate
      if power_curve == "":
        if not headless: 
          self.PowerCurveVariable.set("Choose a power curve under setup menu")
          self.StartAPPbutton.config(state="normal")
          self.StopAPPbutton.config(state="disabled")
        return
      pc_dict = trainer.parse_factors(power_curve)#get power curve dictionary
      if len(pc_dict) != 14:
        if not headless: 
          self.PowerCurveVariable.set("Need 14 levels for power curve")
          self.StartAPPbutton.config(state="normal")
          self.StopAPPbutton.config(state="disabled")
          return
      pc_sorted_keys = sorted(pc_dict.iterkeys())#-1,-0,2,3 etc.
      if debug:print "reset ant stick"
      ant.antreset(dev_ant, debug)#reset dongle
      if debug:print "calibrate ant stick"
      ant.calibrate(dev_ant, debug)#calibrate ANT+ dongle
      if debug:print "calibrate ant stick FE-C"
      ant.master_channel_config(dev_ant, debug)#calibrate ANT+ channel FE-C
      if debug: print "calibrate ant stick HR"
      ant.second_channel_config(dev_ant, debug)#calibrate ANT+ channel HR
      
      if not headless: self.RunoffButton.config(state='disabled')
      else: print "Ctrl-C to exit"
      resistance=0#set initial resistance level
      speed,cadence,power,heart_rate=(0,)*4#initialise values
      grade = False
      target_power = False
      accumulated_power = 0
      heart_beat_event_time = time.time() * 1000
      heart_beat_event_time_start_cycle = time.time() * 1000
      heart_toggle = 0
      heart_beat_count = 0
      switch = True
      cot_start = time.time()
      eventcounter=0
      #p.44 [10] general fe data, [19] eqpt type trainer, [89] acc value time since start in 0.25s r/over 64s, [8c] acc value time dist travelled in m r/over 256m, 
      #[8d] [20] speed lsb msb 0.001m/s, [00] hr, [30] capabilities bit field
      accumulated_time = time.time()*1000
      distance_travelled = 0
      last_dist_time = time.time()*1000
      
      #p.60 [19] specific trainer data, [10] counter rollover 256, [5a] inst cadence, [b0] acc power lsb, [47] acc power msb (r/over 65536W), [1b] inst power lsb, 
      #[01] bits 0-3 inst power MSB bits 4-7 trainer status bit, [30] flags bit field
      last_measured_time = time.time() * 1000
      try:
        while switch == True:
          if debug == True: print "Running", round(time.time() * 1000 - last_measured_time)
          last_measured_time = time.time() * 1000
          if eventcounter >= 256:
            eventcounter = 0

          ###TRAINER- SHOULD WRITE THEN READ 70MS LATER REALLY
          ####################GET DATA FROM TRAINER####################
          if simulatetrainer: 
            speed, pedecho, heart_rate, force_index, cadence = current_speed, 0, current_heart_rate, 5, current_cadence
          else:
            speed, pedecho, heart_rate, force_index, cadence = trainer.receive(dev_trainer) #get data from device
          if speed == "Not Found":
            speed, pedecho, heart_rate, force_index, cadence = 0, 0, 0, 0, 0
            if not headless: self.trainerVariable.set('Cannot read from trainer')
            else: print "Cannot read from trainer"
          else:
            if not headless: self.trainerVariable.set("Trainer detected")
          #print force_index
          factors = pc_dict[pc_sorted_keys[force_index]]
          calc_power=int(speed*factors[0] + factors[1])
          if calc_power <0: calc_power = 0
          if debug == True: print speed, pedecho, heart_rate, force_index, cadence, calc_power
          ####################SEND DATA TO TRAINER####################
          #send resistance data to trainer   
          if debug == True: print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],"GRADE", grade,"%"
          #set resistance level
          if not grade and not target_power:#if trainer not been been set a grade or target power
            grade = 0
          resistance_level = len(pc_dict) - 1#set to highest by default
          if grade is not False:#find resistance for grade
            for idx, g in enumerate(sorted(pc_dict)):
              if g >= grade:#find resistance value immediately above grade set by zwift 
                resistance_level = idx
                break
          elif target_power:#get resistance closest for power target
            if speed < 10:
              speed = 10#default to at least 10 kph
            closest = 1000
            for idx, g in enumerate(sorted(pc_dict)):#iterate up
              power_at_level = int(speed*pc_dict[g][0] + pc_dict[g][1])
              #print idx,g,power_at_level
              if (target_power - power_at_level)**2 < closest ** 2:
                resistance_level = idx
                closest = ((target_power - power_at_level)**2)**0.5
          #print resistance_level
          if not simulatetrainer:
            trainer.send(dev_trainer, resistance_level, pedecho)

            #time.sleep(0.2)#simulated trainer timeout
          ####################BROADCAST AND RECEIVE ANT+ data####################
          if speed == "Not Found":
            speed, pedecho, calc_power, cadence = 0, 0, 0, 0
          if calc_power >= 4094:
            calc_power = 4093
          accumulated_power += calc_power
          if accumulated_power >= 65536:
            accumulated_power = 0

          if (eventcounter + 1) % 66 == 0 or eventcounter % 66 == 0:#send first and second manufacturer's info packet
            newdata = "a4 09 4e 00 50 ff ff 01 0f 00 85 83 bb 00 00"
            
          elif (eventcounter+32) % 66 == 0 or (eventcounter+33) % 66 == 0:#send first and second product info packet
            newdata = "a4 09 4e 00 51 ff ff 01 01 00 00 00 b2 00 00"
          
          elif eventcounter % 3 == 0:#send general fe data every 3 packets
            accumulated_time_counter = int((time.time()*1000 - accumulated_time)/1000/0.25)# time since start in 0.25 seconds
            if accumulated_time_counter >= 256:#rollover at 64 seconds (256 quarter secs)
              accumulated_time_counter = 0
              accumulated_time = time.time()*1000
            newdata = '{0}{1}{2}'.format('a4 09 4e 00 10 19 ', hex(accumulated_time_counter)[2:].zfill(2), ' 8c 8d 20 00 30 72 00 00') # set time
            distance_travelled_since_last_loop = (time.time()*1000 - last_dist_time)/1000 * speed * 1000/3600#speed reported in kph- convert to m/s
            last_dist_time = time.time()*1000#reset last loop time
            distance_travelled += distance_travelled_since_last_loop
            if distance_travelled >= 256:#reset at 256m
              distance_travelled = 0
            newdata = '{0}{1}{2}'.format(newdata[:21], hex(int(distance_travelled))[2:].zfill(2), newdata[23:]) # set distance travelled  
            hexspeed = hex(int(speed*1000*1000/3600))[2:].zfill(4)
            newdata = '{0}{1}{2}{3}{4}'.format(newdata[:24], hexspeed[2:], ' ' , hexspeed[:2], newdata[29:]) # set speed
            newdata = '{0}{1}{2}'.format(newdata[:36], ant.calc_checksum(newdata), newdata[38:])#recalculate checksum

          else:#send specific trainer data
            newdata = '{0}{1}{2}'.format('a4 09 4e 00 19 ', hex(eventcounter)[2:].zfill(2), ' 5a b0 47 1b 01 30 6d 00 00') # increment event count
            if cadence >= 254:
              cadence=253
            newdata = '{0}{1}{2}'.format(newdata[:18], hex(cadence)[2:].zfill(2), newdata[20:])#instant cadence
            hexaccumulated_power = hex(int(accumulated_power))[2:].zfill(4)
            newdata = '{0}{1}{2}{3}{4}'.format(newdata[:21], hexaccumulated_power[2:], ' ' , hexaccumulated_power[:2], newdata[26:]) # set accumulated power
            hexinstant_power = hex(int(calc_power))[2:].zfill(4)
            hexinstant_power_lsb = hexinstant_power[2:]
            newdata = '{0}{1}{2}'.format(newdata[:27], hexinstant_power_lsb, newdata[29:])#set power lsb byte
            hexinstant_power_msb = hexinstant_power[:2]
            bits_0_to_3 = bin(int(hexinstant_power_msb,16))[2:].zfill(4)
            power_msb_trainer_status_byte = '0000' + bits_0_to_3
            newdata = '{0}{1}{2}'.format(newdata[:30], hex(int(power_msb_trainer_status_byte))[2:].zfill(2), newdata[32:])#set mixed trainer data power msb byte
            newdata = '{0}{1}{2}'.format(newdata[:36], ant.calc_checksum(newdata), newdata[38:])#recalculate checksum
          
          if debug == True: print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],"TRAINER DATA",newdata
          reply = ant.send_ant([newdata], dev_ant, debug)
          #reply = []
          #if rv[6:8]=="33":
          #rtn = {'grade' : int(rv[18:20]+rv[16:18],16) * 0.01 - 200} #7% in zwift = 3.5% grade in ANT+  
          matching = [s for s in reply if "a4094f0033" in s]#target resistance
          # 0x33 a4094f00 33 ffffffff964fff f7 is gradient message
          if matching:
            grade = int(matching[0][20:22]+matching[0][18:20],16) * 0.01 - 200
            target_power = False
            if not headless: self.SlopeVariable.set(round(grade,1))
            if not headless: self.TargetPowerVariable.set("")
            if debug: print grade, matching[0]
          else:
            matching = [s for s in reply if "a4094f0031" in s]#target watts
            # 0x31 a4094f00 31 ffffffffff5c02 72 is target power message in 0.25w 0x025c = 604 = 151W
            if matching:
              target_power = int(matching[0][22:24]+matching[0][20:22],16)/4
              grade = False
              if not headless: self.TargetPowerVariable.set(target_power)
              if not headless: self.SlopeVariable.set("")
          ####################HR#######################
          #HR format
          #D00000693_-_ANT+_Device_Profile_-_Heart_Rate_Rev_2.1.pdf
          #[00][FF][FF][FF][55][03][01][48]p. 18 [00] bits 0:6 data page no, bit 7 toggle every 4th message, [ff][ff][ff] (reserved for page 0), [55][03] heart beat event time [lsb][ msb] rollover 64s, [01] heart beat count rollover 256, [instant heart rate]max 256
          #[00][FF][FF][FF][55][03][01][48]
          #[00][FF][FF][FF][AA][06][02][48]
          #[00][FF][FF][FF][AA][06][02][48]
          #[80][FF][FF][FF][AA][06][02][48]
          #[80][FF][FF][FF][AA][06][02][48]
          #[80][FF][FF][FF][FF][09][03][48]
          #[80][FF][FF][FF][FF][09][03][48]
          #[00][FF][FF][FF][FF][09][03][48]
          #[00][FF][FF][FF][54][0D][04][48]
          #[00][FF][FF][FF][54][0D][04][48]
          #[00][FF][FF][FF][54][0D][04][48]
          
          #every 65th message send manufacturer and product info -apge 2 and page 3
          #[82][0F][01][00][00][3A][12][48] - [82] page 2 with toggle on (repeat 4 times)
          #[83][01][01][33][4F][3F][13][48] - [83] page 3 with toggle on 
          #if eventcounter > 40: heart_rate = 100 #comment out in production
          if heart_rate>0:#i.e. heart rate belt attached
            if eventcounter % 4 == 0:#toggle bit every 4 counts
              if heart_toggle == 0: heart_toggle = 128
              else: 
                heart_toggle = 0
            
            #check if heart beat has occurred as tacx only reports instanatenous heart rate data
            #last heart beat is at heart_beat_event_time
            #if now - heart_beat_event_time > time taken for hr to occur, trigger beat. 70 bpm = beat every 60/70 seconds
            if (time.time()*1000 - heart_beat_event_time) >= (60 / float(heart_rate))*1000:
              heart_beat_count += 1#increment heart beat count           
              heart_beat_event_time += (60 / float(heart_rate))*1000#reset last time of heart beat
              
            if heart_beat_event_time - heart_beat_event_time_start_cycle >= 64000:#rollover every 64s
              heart_beat_event_time = time.time()*1000#reset last heart beat event
              heart_beat_event_time_start_cycle = time.time()*1000#reset start of cycle
              
            
            if heart_beat_count >= 256:
              heart_beat_count = 0
            
            if heart_rate >= 256:
              heart_rate = 255
            
            hex_heart_beat_time = int((heart_beat_event_time - heart_beat_event_time_start_cycle)*1.024) # convert ms to 1/1024 of a second
            hex_heart_beat_time = hex(hex_heart_beat_time)[2:].zfill(4)
            
            hr_byte_4 = hex_heart_beat_time[2:]
            hr_byte_5 = hex_heart_beat_time[:2]
            hr_byte_6 = hex(heart_beat_count)[2:].zfill(2)
            hr_byte_7 = hex(heart_rate)[2:].zfill(2)
            
            #data page 1,6,7 every 80s
            if eventcounter % 65 ==0 or (eventcounter + 1) % 65 == 0 or (eventcounter + 2) % 65 == 0 or (eventcounter + 3) % 65 == 0:#send first and second manufacturer's info packet
              hr_byte_0 = hex(2 + heart_toggle)[2:].zfill(2)
              hr_byte_1 = "0f"
              hr_byte_2 = "01"
              hr_byte_3 = "00"
              #[82][0F][01][00][00][3A][12][48]
            elif (eventcounter+31) % 65 == 0 or (eventcounter+32) % 65 == 0 or (eventcounter+33) % 65 == 0 or (eventcounter+34) % 65 == 0:#send first and second product info packet
              hr_byte_0 = hex(3 + heart_toggle)[2:].zfill(2)
              hr_byte_1 = "01"
              hr_byte_2 = "01"
              hr_byte_3 = "33"      
              #[83][01][01][33][4F][3F][13][48]
            elif (eventcounter+11) % 65 == 0 or (eventcounter+12) % 65 == 0 or (eventcounter+13) % 65 == 0 or (eventcounter+44) % 65 == 0:#send page 0x01 cumulative operating time
              cot = int((time.time() - cot_start) / 2)
              cot_hex = hex(cot)[2:].zfill(6)
              hr_byte_0 = hex(1 + heart_toggle)[2:].zfill(2)
              hr_byte_1 = cot_hex[4:6]
              hr_byte_2 = cot_hex[2:4]
              hr_byte_3 = cot_hex[0:2]
            elif (eventcounter+21) % 65 == 0 or (eventcounter+22) % 65 == 0 or (eventcounter+23) % 65 == 0 or (eventcounter+24) % 65 == 0:#send page 0x06 capabilities
              hr_byte_0 = hex(6 + heart_toggle)[2:].zfill(2)
              hr_byte_1 = "ff"
              hr_byte_2 = "00"
              hr_byte_3 = "00"
            elif (eventcounter+41) % 65 == 0 or (eventcounter+42) % 65 == 0 or (eventcounter+43) % 65 == 0 or (eventcounter+44) % 65 == 0:#send page 0x07 battery
              hr_byte_0 = hex(7 + heart_toggle)[2:].zfill(2)
              hr_byte_1 = "64"
              hr_byte_2 = "55"
              hr_byte_3 = "13"
            else:#send page 0
              hr_byte_0 = hex(0 + heart_toggle)[2:].zfill(2)
              hr_byte_1 = "ff"
              hr_byte_2 = "ff"
              hr_byte_3 = "ff"
              
            hrdata = "a4 09 4e 01 "+hr_byte_0+" "+hr_byte_1+" "+hr_byte_2+" "+hr_byte_3+" "+hr_byte_4+" "+hr_byte_5+" "+hr_byte_6+" "+hr_byte_7+" 02 00 00"
            hrdata = "a4 09 4e 01 "+hr_byte_0+" "+hr_byte_1+" "+hr_byte_2+" "+hr_byte_3+" "+hr_byte_4+" "+hr_byte_5+" "+hr_byte_6+" "+hr_byte_7+" "+ant.calc_checksum(hrdata)+" 00 00"
            time.sleep(0.125)# sleep for 125ms
            if debug == True: print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],"HEART RATE",hrdata
            ant.send_ant([hrdata], dev_ant, debug)
          ####################wait ####################

          #add wait so we only send every 250ms
          time_to_process_loop = time.time() * 1000 - last_measured_time
          sleep_time = 0.25 - (time_to_process_loop)/1000
          if sleep_time < 0: sleep_time = 0
          time.sleep(sleep_time)
          eventcounter += 1
          
          if not headless: 
            self.SpeedVariable.set(speed)
            self.HeartrateVariable.set(heart_rate)
            self.CadenceVariable.set(cadence)
            self.PowerVariable.set(calc_power)
            self.ResistanceLevelVariable.set(resistance_level)
          elif eventcounter % 4 == 0:
            print "Power %sW, HR %s, Cadence %s, Resistance %s, Speed %s" % (calc_power, heart_rate, cadence, resistance_level, current_speed)
            
      except KeyboardInterrupt:
        print "Stopped"
        
      ant.antreset(dev_ant, debug)#reset dongle
      if os.name == 'posix':#close serial port to ANT stick on Linux
        dev_ant.close()
      if debug: print "stopped"
      if not headless: self.RunoffButton.config(state='normal')
      
      with open("user_defaults",'wb') as handle:#save defaults
        pickle.dump(user_defaults, handle, protocol=pickle.HIGHEST_PROTOCOL)

    if not headless:
      self.FindHWbutton.config(state="disabled")
      self.StartAPPbutton.config(state="disabled")
      self.StopAPPbutton.config(state="normal")
      thread = threading.Thread(target=run)  
      thread.start() 
    else:
      print "not headless"
      ##run()
      thread = threading.Thread(target=run)  
      thread.start() 
      print "Starting 2nd thread..."
      thread2 = threading.Thread(target=poller)  
      thread2.start() 
      thread.join()
      thread2.join()


def on_closing():#handle for window closing- stop loops
  global switch
  switch = False
  root.destroy()


#load defaults
try:
  user_defaults = pickle.load(open('user_defaults','rb'))
except:
  user_defaults = {}



dev_trainer = False
dev_ant = False
power_curve = ""


if __name__ == "__main__":
  if headless:
    power_curve = args.power_curve
    if not power_curve:
      print "Specify a power curve .txt file with -c switch"
    else:
      x = Window()
      if x.ScanForHW():
        x.Start()
   
  else:
    # root window created. Here, that would be the only window, but
    # you can later have windows within windows.
    root = Tk()

    #root.geometry("30x220")
    #frame = Frame(root)
    #frame.pack()

    #creation of an instance
    app = Window(root)
  #
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
