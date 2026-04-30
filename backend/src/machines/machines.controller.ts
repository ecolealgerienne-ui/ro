import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
} from '@nestjs/common';
import { CreateMachineDto } from './dto/create-machine.dto';
import { UpdateMachineDto } from './dto/update-machine.dto';
import { MachinesService } from './machines.service';

@Controller('workshops/:workshopId/machines')
export class MachinesController {
  constructor(private readonly machines: MachinesService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  create(@Param('workshopId', ParseUUIDPipe) workshopId: string, @Body() dto: CreateMachineDto) {
    return this.machines.create(workshopId, dto);
  }

  @Get()
  findAll(@Param('workshopId', ParseUUIDPipe) workshopId: string) {
    return this.machines.findAll(workshopId);
  }

  @Get(':id')
  findOne(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.machines.findOne(workshopId, id);
  }

  @Patch(':id')
  update(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateMachineDto,
  ) {
    return this.machines.update(workshopId, id, dto);
  }

  @Delete(':id')
  remove(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.machines.remove(workshopId, id);
  }
}
