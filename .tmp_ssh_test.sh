#!/usr/bin/expect -f
set timeout 30
spawn ssh -o StrictHostKeyChecking=no claudetest@claw.fe2fe.top -p 22
expect "password:"
send "ABC1986720abc\r"
expect "$ "
send "echo 'SSH连接成功'; python3 --version; which git; pwd\r"
expect "$ "
send "exit\r"
expect eof
