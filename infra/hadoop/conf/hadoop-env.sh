export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
export HADOOP_LOG_DIR=/opt/hadoop-data/logs

export HDFS_NAMENODE_OPTS="-Xmx2g"
export HDFS_DATANODE_OPTS="-Xmx1g"
export HDFS_SECONDARYNAMENODE_OPTS="-Xmx1g"
export YARN_RESOURCEMANAGER_OPTS="-Xmx1g"
export YARN_NODEMANAGER_OPTS="-Xmx1g"
