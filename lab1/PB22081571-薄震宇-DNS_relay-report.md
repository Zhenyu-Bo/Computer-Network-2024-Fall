# Lab1 - DNS relay

> PB22081571 薄震宇

## 实验目的

本次实验旨在实验一个DNS中继器，处理本机发出的DNS请求，根据本地的配置文件决定如何处理（拦截，本地解析或中继）。

## 实验内容

本次实验只需要补全框架中代码即可，具体来说，需要补全`query_part`类的`unpack`方法和`pack`方法，`message`类的`r_pack`方法，`realy_server`类的`process`方法。下面分别对这几个类中补全的几处代码进行解释。

### query_part

`query_part`表示问题记录，`unpack`方法用于从记录中解析出二进制查询报文的问题节，`pack`方法用于将问题节打包回二进制查询报文。问题节的格式如下图：

![query](figs/query.png)

#### unpack

`unpack`方法用于解析二进制查询报文中的问题节，也即解析出域名，查询类型和查询类别。此外我在框架的基础上添加了一个成员变量`original_name`，用于表示问题节中的域名段，这可以方便后续的打包操作。

要查询的域名会被编码为一些labels序列，每个labels包含一个字节表示后续字符串长度，以及这个字符串，以0长度和空字符串来表示域名结束。这个字段可能为奇数字节，不需要进行边界填充对齐。

所以解析域名时可以使用一个循环，首先读取后续字符串长度，然后再在这个长度范围内读取字符串。读取完成后进行一个判断：如果字符串长度为0则结束循环，否则在读取完字符串后添加`.`到域名中。

假设`data[idx] == 0`，则`data[0:idx+1]`是`labels`段，所以将`data[0:idx+1]`赋值给`original_name`即可。

因为查询类型和查询类别紧跟在域名段后且均占两个字节，所以可以直接使用`struct.unpack('>HH', data[idx + 1: idx + 5])`来读取。

`unpack`方法的代码如下：

```python
def unpack(self, data):
        """
        TODO: 解析二进制查询报文中的问题节，data -> name, type, class
        """
        self.name = ""
        idx = 0
        # 先处理域名
        while True:
            for i in range(idx + 1, idx + 1 + data[idx]):
                # data[idx]表示后续字符串长度（以点分隔）
                self.name += chr(data[i])
            idx += data[idx] + 1
            if data[idx] == 0:
                break
            self.name += '.'
        self.original_name = data[0:idx+1]  # 获得原始域名段
        self.type, self.classify = struct.unpack('>HH', data[idx + 1: idx + 5])
```

#### pack

`pack`方法用于将问题节打包回二进制查询报文，只需要将`self.original_name`，`self.type`和`self.classify`这三个数据成员依次写入二进制报文`data`中并返回即可。

我首先初始化了一个`bytearray`对象`data`来存储返回值，然后使用`extend`方法将`original_name`添加到`data`中，因为查询类型和查询类别紧跟在域名段后且均占两个字节，所以可以直接使用`struct.pack('>HH', self.type, self.classify)`将这两个字段添加到报文中。

代码如下：

```python
def pack(self):
        """
        打包回二进制
        TODO: 将问题节打包回二进制查询报文，name, type, class -> data
        """
        data = bytearray()
        data.extend(self.original_name)
        data += struct.pack('>HH', self.type, self.classify)
        return data
```

### message

`message`类表示查询报文，`r_pack`方法用于根据ip资源和当前查询报文内容生成回复报文。

