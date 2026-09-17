package com.cyberrag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cyberrag.entity.User;
import org.apache.ibatis.annotations.Mapper;

/**
 * `user` 表 Mapper。
 */
@Mapper
public interface UserMapper extends BaseMapper<User> {
}
