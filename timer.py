import datetime
import yaml
import time

class CellBalancing ():
   __lastSOC = 0
   __timerStartTime = datetime.datetime.now()
   holdSOC = 99                #SOC to hold at when actual SOC is greater than this value
   cellBalancingInterval = 1  #day interval to perform cell balancing
   cellBalancingMinutes = 1  #number of minutes to balance
   isCellBalancingActive = False
   remainingTime = 0

   def __evaluateDay (self):
      return True
   
   def __startTimer (self):
      self.__timerStartTime = datetime.datetime.now()
      self.isCellBalancingActive = True

   def __stopTimer (self):
      self.isCellBalancingActive = False
    
   def __remainingTime (self):
      elapsedTime = datetime.datetime.now() - self.__timerStartTime
      print ('elapsed time:' + str(elapsedTime))
      return (self.cellBalancingMinutes * 60) - elapsedTime.seconds

   
   def evaluateSOC(self, SOC):
      if (self.__lastSOC == 0): self.__lastSOC = SOC

      if (self.isCellBalancingActive):
         self.remainingTime = self.__remainingTime()
         print ('1')
         if (self.remainingTime > 0):
            return self.holdSOC
         else:
            self.__stopTimer()
      else:
         #evaluate if we have reached the start of hold
         if (SOC > self.__lastSOC):
            self.__lastSOC = SOC
            if (SOC > self.holdSOC):
               #start timer if we are on an active day
               if self.__evaluateDay():
                  self.__startTimer()
                  return self.holdSOC
      
      return SOC

#region ************** main **************
def main():
   cb = CellBalancing()

   SOC = cb.evaluateSOC(99)
   time.sleep(1)
   SOC = cb.evaluateSOC(100)

   while True:
      SOC = cb.evaluateSOC(100)
      print ("Fakeout SOC:" + str(SOC))
      print ("time remaining: " + str(cb.remainingTime))
      print ('is cell balancing: ' + str(cb.isCellBalancingActive))
      time.sleep(1)
      


      


#application entry point:
if __name__ == "__main__":
   with open ("config/BMS2Inverter.yaml") as f:
      config = yaml.load(f, Loader=yaml.FullLoader)


   main()                  # call the main function: