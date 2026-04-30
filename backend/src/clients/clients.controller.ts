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
import { ClientsService } from './clients.service';
import { CreateClientDto } from './dto/create-client.dto';
import { UpdateClientDto } from './dto/update-client.dto';

@Controller('workshops/:workshopId/clients')
export class ClientsController {
  constructor(private readonly clients: ClientsService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  create(@Param('workshopId', ParseUUIDPipe) workshopId: string, @Body() dto: CreateClientDto) {
    return this.clients.create(workshopId, dto);
  }

  @Get()
  findAll(@Param('workshopId', ParseUUIDPipe) workshopId: string) {
    return this.clients.findAll(workshopId);
  }

  @Get(':id')
  findOne(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.clients.findOne(workshopId, id);
  }

  @Patch(':id')
  update(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateClientDto,
  ) {
    return this.clients.update(workshopId, id, dto);
  }

  @Delete(':id')
  remove(
    @Param('workshopId', ParseUUIDPipe) workshopId: string,
    @Param('id', ParseUUIDPipe) id: string,
  ) {
    return this.clients.remove(workshopId, id);
  }
}
