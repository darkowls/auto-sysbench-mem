#!/bin/python3
# sysbench memory --threads=96 --memory-block-size=8K --memory-scope=global --memory-total-size=3072G --memory-oper=write --memory-access-mode=seq run
# sysbench --test=memory --num-threads=96 --memory-block-size=1K --memory-scope=local --memory-total-size=84G --memory-oper=write run\
#Total operations: 88080384 (141909244.29 per second)
#86016.00 MiB transferred (138583.25 MiB/sec)
#
#
#General statistics:
#    total time:                          0.6194s
#    total number of events:              88080384
#
#Latency (ms):
#         min:                                    0.00
#         avg:                                    0.00
#         max:                                   60.01
#         95th percentile:                        0.00
#         sum:                                11618.03
#
#Threads fairness:
#    events (avg/stddev):           917504.0000/0.00
#    execution time (avg/stddev):   0.1210/0.03

import subprocess							# For launching Sysbench
import multiprocessing							# Solely for detecting number of threads
import statistics							# Solely for mean,median and stdev (Python 3 only)
import csv								# For exporting results to CSV file for Excel etc processing
from datetime import datetime						# for CSV unique naming

# Test settings
iterations=3								# Number of repeating each test for fidelity
rampass=2								# testing RAM to make that many passes in each test (1 is for faster run, 4 for running troughy 4 times amount of allocated RAM)
divider=1								# Divider to reduce tested volumes of RAM. 8 for speed (debug), 1 for full RAM size.
threads_increment=4							# Step in which we start with and increment. 4 by default, so we test 4, 8, 12 etc. 8 max recommended.

#General variables
mem_total=0                                                             # Total RAM
mem_free=0                                                              # Free RAM
mem_avail=0 								# RAM available for testing

#Per-iterations variables
iter_MiBps=[]								# list for Mibibytes per second transferred - main parameter - per run
iter_time=[]								# list for storing execution time per run
iter_events=[]								# list for storing number of events per run (same as operations?)
iter_latmin=[]                                                          # list for maximum latency per run
iter_latavg=[]                                                          # list for storing average latency per run
iter_latmax=[]                                                          # list for maximum latency per run
iter_lat95pct=[]							# list for 95 percentile latency per run
iter_latsum=[]								# list for sum of latency (IDK what is it) per run
iter_threventsavg=[]							# list for threads fairness - average event per thread
iter_threventsstdev=[]							# list for threads fairness - events per thread deviation
iter_thrtimeavg=[]							# list for threads fairness - time average per thread
iter_thrtimestdev=[]							# list for threads fairness - time per thread deviation
memscope=[]								# Storing input parameters for CSV
memmode=[]
memoper=[]
memthreads=[]
membuffer=[]
medianEPS=[]								# storing median value from several iterations for specific threads run
averageEPS=[]								# storing average value from several iterations for specific threads run 
stdevEPS=[]								# storing standard deviation for specific threads run
minEPS=[]								# Storing absolute minimum EPS for specific threads run
maxEPS=[]								# Storing absolute maximunm EPS for specific threads run
medianMiBps=[]                                                          # storing median value from several iterations for specific threads run
averageMiBps=[]                                                         # storing average value from several iterations for specific threads run
stdevMiBps=[]                                                           # storing standard deviation for specific threads run
minMiBps=[]                                                             # Storing absolute minimum EPS for specific threads run
maxMiBps=[]                                                             # Storing absolute maximunm EPS for specific threads run
run_time=[]								# Storing run time of every execution
latmin=[]								# Storing minimum latency for specific threads run
latavg=[]								# Storing average latency for specific threads run
latmax=[]								# Storing maximum latency for specific threads run
latper=[]								# Storing latency for 95% percentile for specific threads run
threventsavg=[]                                                    	# list for threads fairness - average event per thread
threventsstdev=[]                                                 	# list for threads fairness - events per thread deviation
thrtimeavg=[]                                                      	# list for threads fairness - time average per thread
thrtimestdev=[]                                                   	# list for threads fairness - time per thread deviation

csvname=""								# CSV filename

# Detecting CPU threads
detected_threads=multiprocessing.cpu_count()				# Detecting CPU threads
max_threads=round(detected_threads*1.2/8)*8                             # Adding aproxumately 20 % of threads (incremented by 8) for testing beyond CPU threads
# Detecting total and free available RAM
with open('/proc/meminfo') as file:					# It writes outputs in "kB" - but it is really KiB
	for line in file:
		if "MemFree" in line:
			mem_free = int(int(line.split()[1])/1024)	# Free mem in MiB (sysbench counts in MiB)
		if "MemTotal" in line:
			mem_total=int(int(line.split()[1])/1024)	# Total mem in MiB

mem_per_core=round(mem_total/detected_threads)				# Memory per core in MiB


####REFACTORING FROM HERE
# Finding basic and maximum block size in powers of 2 (also, block size for all threads in global mode)
block_size=1								# starting with 1 MiB (sysbench does not work great with 1K-128K size buffer, shows low speed)
while(block_size*2<int(mem_per_core/divider) and block_size*2*detected_threads<mem_free):
	block_size=block_size*2
total_size=block_size							# We pick maximum block size which is possible to malloc per core, not 100% (we can't run out of memory)
while(total_size*2<int(mem_free/divider)):				# But in global mode we might take more RAM (more when just by multiplying per core)
	total_size=total_size*2						# It might stay the same, or might be 2* times more (probably).
work_size=int(total_size*rampass/1024)					# Total number of data processed on each run in GiB - taking number of passes into account

print ("Detected "+str(detected_threads)+" threads, "+str(mem_per_core)+" MiB RAM per thread")
print ("Memory total: "+str(mem_total)+" MiB; free: "+str(mem_free)+"MiB")
print ("Testing with buffer size up to "+str(block_size)+"MiB per core, up to "+str(total_size)+" MiB total, processing "+str(work_size)+" GiB on each pass")
for memory_scope in ("global","local"):					# testing in both global and local modes
	if memory_scope=="global":
		buffer_size=total_size
	else:
		buffer_size=block_size
	print("Memory Scope:"+memory_scope+", Maximum buffer size:"+str(buffer_size)+"MiB, Work Size:"+str(work_size)+"GiB")
	for memory_access_mode in ("seq","rnd"):			# testing in both sequental and random modes
		for memory_oper in ("read","write"):			# Testing in both read in write modes
			print("Mode:",memory_scope,memory_access_mode,memory_oper)
			threads=threads_increment			# We do not suppose modern CPUs having less then 4 threads, by default we increment also by 4 threads
			while(threads<=detected_threads):
				buf_size=1				# Resetting start buffer to 1 Mb
				while(buf_size<=buffer_size):
					print("[Threads:"+str(threads)+"/"+str(buf_size)+"MiB]",end="",flush=True)
					for iter in range(0,iterations):
						print("*",end="",flush=True)
						bashCommand="sysbench memory --threads="+str(threads)+" --memory-block-size="+str(buf_size)+"M --memory-scope="+memory_scope+" --memory-total-size="+str(work_size)+"G --memory-oper="+memory_oper+" --memory-access-mode="+memory_access_mode+" run"
#						print(bashCommand)
						sysbench_output=subprocess.run([bashCommand],shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8')
						if sysbench_output.returncode==0:	# If command completed successfully
							value_beg=sysbench_output.stdout.find("total number of events:")+23
							value_end=sysbench_output.stdout.find("\n",value_beg)
							iter_events.append(int(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("transferred (")+13
							value_end=sysbench_output.stdout.find(" MiB/sec)\n",value_beg)
							iter_MiBps.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("total time:")+11
							value_end=sysbench_output.stdout.find("s\n",value_beg)
							iter_time.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("min:")+4
							value_end=sysbench_output.stdout.find("\n",value_beg)
							iter_latmin.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("avg:")+4
							value_end=sysbench_output.stdout.find("\n",value_beg)
							iter_latavg.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("max:")+4
							value_end=sysbench_output.stdout.find("\n",value_beg)
							iter_latmax.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("95th percentile:")+16
							value_end=sysbench_output.stdout.find("\n",value_beg)
							iter_lat95pct.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("events (avg/stddev):")+20
							value_end=sysbench_output.stdout.find("/",value_beg)
							iter_threventsavg.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("/",value_end)+1
							value_end=sysbench_output.stdout.find("\n",value_beg-1)
							iter_threventsstdev.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("execution time (avg/stddev):")+28
							value_end=sysbench_output.stdout.find("/",value_beg)
							iter_thrtimeavg.append(float(sysbench_output.stdout[value_beg:value_end]))
							value_beg=sysbench_output.stdout.find("/",value_end)+1
							value_end=sysbench_output.stdout.find("\n",value_beg)
							iter_thrtimestdev.append(float(sysbench_output.stdout[value_beg:value_end]))
						else:					# if Sysbench failed
							print("Error occured"+sysbench_output.stderr)
							exit
					print("DONE: "+str(statistics.median(iter_MiBps))+"MiB/s")
					buf_size=buf_size*2				# Increasing buffer size by 2
					memthreads.append(threads)
					membuffer.append(buf_size)
					memscope.append(memory_scope)
					memmode.append(memory_access_mode)
					memoper.append(memory_oper)
					medianEPS.append(statistics.median(iter_events))
					averageEPS.append(statistics.mean(iter_events))
					if len(iter_events)>1:
						stdevEPS.append(statistics.stdev(iter_events))
					else:
						stdevEPS.append(0)
					minEPS.append(min(iter_events))
					maxEPS.append(max(iter_events))
					if len(iter_MiBps)>1:
						medianMiBps.append(statistics.median(iter_MiBps))
						averageMiBps.append(statistics.mean(iter_MiBps))
						stdevMiBps.append(statistics.stdev(iter_MiBps))
					else:
						medianMiBps.append(0)
						averageMiBps.append(0)
						stdevMiBps.append(0)
					minMiBps.append(min(iter_MiBps))
					maxMiBps.append(max(iter_MiBps))
					if len(iter_time)>1:
						run_time.append(statistics.median(iter_time))
					else:
						run_time.append(0)
					latmin.append(min(iter_latmin))
					if len(iter_latavg)>1:
						latavg.append(statistics.mean(iter_latavg))
					else:
						latavg.append(0)
					latmax.append(max(iter_latmax))
					if len(iter_lat95pct)>1:
						latper.append(statistics.mean(iter_lat95pct))
					else:
						latper.append(0)
					if len(iter_threventsavg)>1:
						threventsavg.append(statistics.mean(iter_threventsavg))
					else:
						threventsavg.append(0)
					if len(iter_threventsstdev)>1:
						threventsstdev.append(statistics.mean(iter_threventsstdev))
					else:
						threventsstdev.append(0)
					if len(iter_thrtimeavg)>1:
						thrtimeavg.append(statistics.mean(iter_thrtimeavg))
					else:
						thrtimeavg.append(0)
					if len(iter_thrtimestdev)>1:
						thrtimestdev.append(statistics.mean(iter_thrtimestdev))
					else:
						thrtimestdev.append(0)

					iter_events.clear()		# We need to clear it all for the next threads run
					iter_MiBps.clear()
					iter_time.clear()
					iter_latmin.clear()
					iter_latavg.clear()
					iter_latmax.clear()
					iter_lat95pct.clear()
					iter_threventsavg.clear()
					iter_threventsstdev.clear()
					iter_thrtimeavg.clear()
					iter_thrtimestdev.clear()
				threads=threads+threads_increment
# Exporting results to CSV file
dateTimeObj=datetime.now()						# Getting current date and time
dateTimeStr=dateTimeObj.strftime("%Y%m%d_%H%M%S")			# Formatting date to simplify naming
csvname="mem_"+dateTimeStr+".csv"					# defining name for CSV file
print(csvname + " written")
with open(csvname,"w",newline="") as csvfile:
	writer=csv.writer(csvfile)
	writer.writerow(["threads","buffer_size","mem_scope","mem_access_mode","mem_operation","events_median","events_avg","events_stdev","events_min","events_max","run_time","lat_min","lat_avg","lat_max","lat_per95","thread_events_avg","thread_events_stdev","thread_time_avg","thread_time_stdev"])
	print(len(maxEPS))
	for i in range(0, len(maxEPS)):
		writer.writerow([str(i+1),memthreads[i],membuffer[i],memscope[i],memmode[i],memoper[i],medianEPS[i],averageEPS[i],stdevEPS[i],minEPS[i],maxEPS[i],medianMiBps[i],averageMiBps[i],stdevMiBps[i],minMiBps[i],maxMiBps[i],run_time[i],latmin[i],latavg[i],latmax[i],latper[i],threventsavg[i],threventsstdev[i],thrtimeavg[i],thrtimestdev[i]])
#		print(str(i+1),memthreads[i],membuffer[i],memscope[i],memmode[i],memoper[i],medianEPS[i],averageEPS[i],stdevEPS[i],minEPS[i],maxEPS[i],medianMiBps[i],averageMiBps[i],stdevMiBps[i],minMiBps[i],maxMiBps[i],run_time[i],latmin[i],latavg[i],latmax[i],latper[i],threventsavg[i],threventsstdev[i],thrtimeavg[i],thrtimestdev[i])
